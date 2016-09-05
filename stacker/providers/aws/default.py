import json
import logging
import os
import time

import boto3
import botocore.exceptions

from ..base import BaseProvider
from ... import exceptions
from ...util import retry_with_backoff

logger = logging.getLogger(__name__)

MAX_TAIL_RETRIES = 5


def get_output_dict(stack):
    """Returns a dict of key/values for the outputs for a given CF stack.

    Args:
        stack (dict): The stack object to get
            outputs from.

    Returns:
        dict: A dictionary with key/values for each output on the stack.

    """
    outputs = {}
    for output in stack['Outputs']:
        logger.debug("    %s %s: %s", stack['StackName'], output['OutputKey'],
                     output['OutputValue'])
        outputs[output['OutputKey']] = output['OutputValue']
    return outputs


def retry_on_throttling(fn, attempts=3, args=None, kwargs=None):
    """Wrap retry_with_backoff to handle AWS Cloudformation Throttling.

    Args:
        fn (function): The function to call.
        attempts (int): Maximum # of attempts to retry the function.
        args (list): List of positional arguments to pass to the function.
        kwargs (dict): Dict of keyword arguments to pass to the function.

    Returns:
        passthrough: This returns the result of the function call itself.

    Raises:
        passthrough: This raises any exceptions the function call raises,
            except for boto.exception.BotoServerError, provided it doesn't
            retry more than attempts.
    """
    def _throttling_checker(exc):
        """

        Args:
        exc (botocore.exceptions.ClientError): Expected exception type

        Returns:
             boolean: indicating whether this error is a throttling error
        """
        if exc.response['ResponseMetadata']['HTTPStatusCode'] == 400 and \
                exc.response['Error']['Code'] == "Throttling":
            logger.debug("AWS throttling calls.")
            return True
        return False

    return retry_with_backoff(fn, args=args, kwargs=kwargs, attempts=attempts,
                              exc_list=(botocore.exceptions.ClientError, ),
                              retry_checker=_throttling_checker)


class Provider(BaseProvider):
    """AWS CloudFormation Provider"""

    DELETED_STATUS = "DELETE_COMPLETE"
    IN_PROGRESS_STATUSES = (
        "CREATE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_IN_PROGRESS",
        "DELETE_IN_PROGRESS",
    )
    COMPLETE_STATUSES = (
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
    )

    def __init__(self, region, **kwargs):
        self.region = region
        self._outputs = {}
        self._cloudformation = None
        # Necessary to deal w/ multiprocessing issues w/ sharing ssl conns
        # see: https://github.com/remind101/stacker/issues/196
        self._pid = os.getpid()

    @property
    def cloudformation(self):
        # deals w/ multiprocessing issues w/ sharing ssl conns
        # see https://github.com/remind101/stacker/issues/196
        pid = os.getpid()
        if pid != self._pid or not self._cloudformation:
            session = boto3.Session(region_name=self.region)
            self._cloudformation = session.client('cloudformation')
        return self._cloudformation

    def get_stack(self, stack_name, **kwargs):
        try:
            return retry_on_throttling(
                self.cloudformation.describe_stacks,
                kwargs=dict(StackName=stack_name))['Stacks'][0]
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

    def get_stack_status(self, stack, **kwargs):
        return stack['StackStatus']

    def is_stack_completed(self, stack, **kwargs):
        return self.get_stack_status(stack) in self.COMPLETE_STATUSES

    def is_stack_in_progress(self, stack, **kwargs):
        return self.get_stack_status(stack) in self.IN_PROGRESS_STATUSES

    def is_stack_destroyed(self, stack, **kwargs):
        return self.get_stack_status(stack) == self.DELETED_STATUS

    def tail_stack(self, stack, retries=0, **kwargs):
        def log_func(e):
            event_args = [e['ResourceStatus'], e['ResourceType'],
                          e.get('ResourceStatusReason', None)]
            # filter out any values that are empty
            event_args = [arg for arg in event_args if arg]
            template = " ".join(["[%s]"] + ["%s" for _ in event_args])
            logger.info(template, *([stack.fqn] + event_args))

        if not retries:
            logger.info("Tailing stack: %s", stack.fqn)

        try:
            self.tail(stack.fqn,
                      log_func=log_func,
                      include_initial=False)
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.message and retries < MAX_TAIL_RETRIES:
                # stack might be in the process of launching, wait for a second
                # and try again
                time.sleep(1)
                self.tail_stack(stack, retries=retries + 1, **kwargs)
            else:
                raise

    @staticmethod
    def _tail_print(e):
        print("%s %s %s" % (e['ResourceStatus'],
                            e['ResourceType'],
                            e['EventId']))

    def get_events(self, stackname):
        """Get the events in batches and return in chronological order"""
        next_token = None
        event_list = []
        while 1:
            if next_token is not None:
                events = self.cloudformation.describe_stack_events(
                    StackName=stackname, NextToken=next_token
                )
            else:
                events = self.cloudformation.describe_stack_events(
                    StackName=stackname
                )
            event_list.append(events['StackEvents'])
            next_token = events.get('NextToken', None)
            if next_token is None:
                break
            time.sleep(1)
        return reversed(sum(event_list, []))

    def tail(self, stack_name, log_func=_tail_print, sleep_time=5,
             include_initial=True):
        """Show and then tail the event log"""
        # First dump the full list of events in chronological order and keep
        # track of the events we've seen already
        seen = set()
        initial_events = self.get_events(stack_name)
        for e in initial_events:
            if include_initial:
                log_func(e)
            seen.add(e['EventId'])

        # Now keep looping through and dump the new events
        while 1:
            events = self.get_events(stack_name)
            for e in events:
                if e['EventId'] not in seen:
                    log_func(e)
                    seen.add(e['EventId'])
            time.sleep(sleep_time)

    def destroy_stack(self, stack, **kwargs):
        logger.debug("Destroying stack: %s" % (self.get_stack_name(stack)))
        retry_on_throttling(self.cloudformation.delete_stack,
                            kwargs=dict(StackName=self.get_stack_name(stack)))
        return True

    def create_stack(self, fqn, template_url, parameters, tags, **kwargs):
        logger.debug("Stack %s not found, creating.", fqn)
        logger.debug("Using parameters: %s", parameters)
        logger.debug("Using tags: %s", tags)
        retry_on_throttling(
            self.cloudformation.create_stack,
            kwargs=dict(StackName=fqn,
                        TemplateURL=template_url,
                        Parameters=parameters,
                        Tags=tags,
                        Capabilities=["CAPABILITY_IAM"]),
        )
        return True

    def update_stack(self, fqn, template_url, parameters, tags, **kwargs):
        try:
            logger.debug("Attempting to update stack %s.", fqn)
            retry_on_throttling(
                self.cloudformation.update_stack,
                kwargs=dict(StackName=fqn,
                            TemplateURL=template_url,
                            Parameters=parameters,
                            Tags=tags,
                            Capabilities=["CAPABILITY_IAM"]),
            )
        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed." in e.message:
                logger.debug(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            raise
        return True

    def get_stack_name(self, stack, **kwargs):
        return stack['StackName']

    def get_outputs(self, stack_name, *args, **kwargs):
        if stack_name not in self._outputs:
            stack = self.get_stack(stack_name)
            self._outputs[stack_name] = get_output_dict(stack)
        return self._outputs[stack_name]

    def get_stack_info(self, stack_name):
        """ Get the template and parameters of the stack currently in AWS

        Returns [ template, parameters ]
        """
        try:
            stacks = retry_on_throttling(
                self.cloudformation.describe_stacks,
                kwargs=dict(StackName=stack_name))
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

        try:
            template = retry_on_throttling(
                self.cloudformation.get_template,
                kwargs=dict(StackName=stack_name))['TemplateBody']
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

        stack = stacks['Stacks'][0]
        parameters = dict()
        if 'Parameters' in stack:
            for p in stack['Parameters']:
                parameters[p['ParameterKey']] = p['ParameterValue']

        return [json.dumps(template), parameters]
