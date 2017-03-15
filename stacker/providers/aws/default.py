import json
import logging
import os

import botocore
from ..base import BaseProvider
from ... import exceptions
from ...util import retry_with_backoff
from stacker.session_cache import get_session
from cloudsns.cloudlistener import CloudListener
from stacker.status import (
    SubmittedStatus,
    CompleteStatus,
)

logger = logging.getLogger(__name__)

MAX_TAIL_RETRIES = 5

LISTENER_NAME = "StackerSNSListener"


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

    IN_PROGRESS_STATUSES = (
        "CREATE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_IN_PROGRESS",
        "DELETE_IN_PROGRESS",
    )
    COMPLETE_STATUSES = (
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "DELETE_COMPLETE"
    )

    def __init__(self, region, **kwargs):
        self.region = region
        self._outputs = {}
        self._cloudformation = None
        self._listener = None
        # Necessary to deal w/ multiprocessing issues w/ sharing ssl conns
        # see: https://github.com/remind101/stacker/issues/196
        self._pid = os.getpid()

    @property
    def cloudformation(self):
        # deals w/ multiprocessing issues w/ sharing ssl conns
        # see https://github.com/remind101/stacker/issues/196
        pid = os.getpid()
        if pid != self._pid or not self._cloudformation:
            session = get_session(self.region)
            self._cloudformation = session.client('cloudformation')

        return self._cloudformation

    @property
    def listener(self, existing_topic_arn=None):
        # deals w/ multiprocessing issues w/ sharing ssl conns
        # see https://github.com/remind101/stacker/issues/196
        pid = os.getpid()
        if pid != self._pid or not self._listener:
            session = get_session(self.region)
            self._listener = CloudListener(
                LISTENER_NAME,
                session=session,
                existing_topic_arn=existing_topic_arn
            )
            self._listener.start()

        return self._listener

    def poll_events(self, tail):
        messages = self.listener.get_messages()
        status_dict = {}

        for message in messages:
            status_dict[message.StackName] = self.get_status(message)
            if tail:
                Provider._tail_print(message)

        if messages:
            self.listener.delete_messages(messages)

        return status_dict

    def cleanup(self):
        self.listener.close()

    def get_status(self, message):
        status_name = message.ResourceStatus

        if status_name in self.COMPLETE_STATUSES:
            return CompleteStatus(status_name)
        elif status_name in self.IN_PROGRESS_STATUSES:
            return SubmittedStatus(status_name)

        raise exceptions.UnknownStatus(
            message.StackName,
            status_name,
            message.ResourceStatusReason
        )

    def destroy_stack(self, stack_name, **kwargs):
        logger.debug("Destroying stack: %s" % (stack_name))
        try:
            return retry_on_throttling(self.cloudformation.delete_stack,
                                       kwargs=dict(StackName=stack_name))

        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.message:
                raise exceptions.StackDoesNotExist(stack_name)

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
                        Capabilities=["CAPABILITY_NAMED_IAM"],
                        NotificationARNs=[self.listener.TopicArn]),
        )
        return True

    def get_stack(self, stack_name):
        try:
            return retry_on_throttling(
                self.cloudformation.describe_stacks,
                kwargs=dict(StackName=stack_name))['Stacks'][0]
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

    def update_stack(self, fqn, template_url, parameters, tags, **kwargs):
        try:
            logger.debug("Attempting to update stack %s.", fqn)
            retry_on_throttling(
                self.cloudformation.update_stack,
                kwargs=dict(StackName=fqn,
                            TemplateURL=template_url,
                            Parameters=parameters,
                            Tags=tags,
                            Capabilities=["CAPABILITY_NAMED_IAM"],
                            NotificationARNs=[self.listener.TopicArn]),
            )
        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed." in e.message:
                logger.debug(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            if "does not exist" in e.message:
                raise exceptions.StackDoesNotExist(fqn)
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
