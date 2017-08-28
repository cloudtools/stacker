import json
import yaml
import logging
import os
import time
import urlparse

import botocore.exceptions

from ..base import BaseProvider
from ... import exceptions
from ...util import retry_with_backoff
from stacker.session_cache import get_session

from ...actions.diff import (
    DictValue,
    diff_parameters,
    format_params_diff as format_diff
)

logger = logging.getLogger(__name__)

MAX_TAIL_RETRIES = 5


def template_args(template):
    """Given a template object, this will return a dict that can be used in
    CreateStack/UpdateStack calls, based on whether or not the template is
    inline, or uploaded to S3.

    Args:
        template (:class:`stacker.providers.base.Template`): The template
            object.

    """
    if template.url:
        return {'TemplateURL': template.url}
    else:
        return {'TemplateBody': template.body}


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


def s3_fallback(fqn, template_url, parameters, tags, method,
                change_set_name=None):
    logger.warn("DEPRECATION WARNING: Falling back to legacy "
                "stacker S3 bucket region for templates. See "
                "http://stacker.readthedocs.io/en/latest/config.html#s3-bucket"
                " for more information.")
    # extra line break on purpose to avoid status updates removing URL
    # from view
    logger.warn("\n")
    logger.debug("Modifying the S3 TemplateURL to point to "
                 "us-east-1 endpoint")
    template_url_parsed = urlparse.urlparse(template_url)
    template_url_parsed = template_url_parsed._replace(
        netloc="s3.amazonaws.com")
    template_url = urlparse.urlunparse(template_url_parsed)
    logger.debug("Using template_url: %s", template_url)
    kwargs = dict(StackName=fqn,
                  TemplateURL=template_url,
                  Parameters=parameters,
                  Tags=tags,
                  Capabilities=["CAPABILITY_NAMED_IAM"],
                  )
    if change_set_name:
        kwargs['ChangeSetName'] = change_set_name
    response = retry_on_throttling(method, kwargs=kwargs)
    return response


def get_change_set_name():
    """Return a valid Change Set Name.

    The name has to satisfy the following regex:
        [a-zA-Z][-a-zA-Z0-9]*

    And must be unique across all change sets.

    """
    return 'change-set-{}'.format(int(time.time()))


def requires_replacement(changeset):
    """Return the changes within the changeset that require replacement.

    Args:
        changeset (list): List of changes

    Returns:
        list: A list of changes that require replacement, if any.

    """
    return [r for r in changeset if r["ResourceChange"].get(
            "Replacement", False) == "True"]


def get_raw_input(message):
    """ Just a wrapper for raw_input for testing purposes. """
    return raw_input(message)


def ask_for_approval(full_changeset=None, params_diff=None,
                     include_verbose=False):
    """Prompt the user for approval to execute a change set.

    Args:
        full_changeset (list, optional): A list of the full changeset that will
            be output if the user specifies verbose.
        params_diff (list, optional): A list of DictValue detailing the
            differences between two parameters returned by
            :func:`stacker.actions.diff.diff_dictionaries`
        include_verbose (bool, optional): Boolean for whether or not to include
            the verbose option

    """
    approval_options = ['y', 'n']
    if include_verbose:
        approval_options.append('v')

    approve = get_raw_input("Execute the above changes? [{}] ".format(
        '/'.join(approval_options)))

    if include_verbose and approve == "v":
        if params_diff:
            logger.info(
                "Full changeset:\n\n%s\n%s",
                format_params_diff(params_diff),
                yaml.safe_dump(full_changeset),
            )
        else:
            logger.info(
                "Full changeset:\n%s",
                yaml.safe_dump(full_changeset),
            )
        return ask_for_approval()
    elif approve != "y":
        raise exceptions.CancelExecution


def output_summary(fqn, action, changeset, params_diff,
                   replacements_only=False):
    """Log a summary of the changeset.

    Args:
        fqn (string): fully qualified name of the stack
        action (string): action to include in the log message
        changeset (list): AWS changeset
        params_diff (list): A list of dictionaries detailing the differences
            between two parameters returned by
            :func:`stacker.actions.diff.diff_dictionaries`
        replacements_only (bool, optional): boolean for whether or not we only
            want to list replacements

    """
    replacements = []
    changes = []
    for change in changeset:
        resource = change['ResourceChange']
        replacement = resource.get('Replacement') == 'True'
        summary = '- %s %s (%s)' % (
            resource['Action'],
            resource['LogicalResourceId'],
            resource['ResourceType'],
        )
        if replacement:
            replacements.append(summary)
        else:
            changes.append(summary)

    summary = ''
    if params_diff:
        summary += summarize_params_diff(params_diff)
    if replacements:
        if not replacements_only:
            summary += 'Replacements:\n'
        summary += '\n'.join(replacements)
    if changes:
        if summary:
            summary += '\n'
        summary += 'Changes:\n%s' % ('\n'.join(changes))
    logger.info('%s %s:\n%s', fqn, action, summary)


def format_params_diff(params_diff):
    """ Just a wrapper for stacker.actions.diff.format_params_diff
    for testing purposes.
    """
    return format_diff(params_diff)


def summarize_params_diff(params_diff):
    summary = ''

    added_summary = [v.key for v in params_diff
                     if v.status() is DictValue.ADDED]
    if added_summary:
        summary += 'Parameters Added: %s\n' % ', '.join(added_summary)

    removed_summary = [v.key for v in params_diff
                       if v.status() is DictValue.REMOVED]
    if removed_summary:
        summary += 'Parameters Removed: %s\n' % ', '.join(removed_summary)

    modified_summary = [v.key for v in params_diff
                        if v.status() is DictValue.MODIFIED]
    if modified_summary:
        summary += 'Parameters Modified: %s\n' % ', '.join(modified_summary)

    return summary


def wait_till_change_set_complete(cfn_client, change_set_id, try_count=25,
                                  sleep_time=.5, max_sleep=3):
    """ Checks state of a changeset, returning when it is in a complete state.

    Since changesets can take a little bit of time to get into a complete
    state, we need to poll it until it does so. This will try to get the
    state `try_count` times, waiting `sleep_time` * 2 seconds between each try
    up to the `max_sleep` number of seconds. If, after that time, the changeset
    is not in a complete state it fails. These default settings will wait a
    little over one minute.

    Args:
        cfn_client (:class:`botocore.client.CloudFormation`): Used to query
            cloudformation.
        change_set_id (str): The unique changeset id to wait for.
        try_count (int): Number of times to try the call.
        sleep_time (int): Time to sleep between attempts.
        max_sleep (int): Max time to sleep during backoff

    Return:
        dict: The response from cloudformation for the describe_change_set
            call.
    """
    complete = False
    response = None
    for i in range(try_count):
        response = retry_on_throttling(
            cfn_client.describe_change_set,
            kwargs={
                'ChangeSetName': change_set_id,
            },
        )
        complete = response["Status"] in ("FAILED", "CREATE_COMPLETE")
        if complete:
            break
        if sleep_time == max_sleep:
            logger.debug(
                "Still waiting on changeset for another %s seconds",
                sleep_time
            )
        time.sleep(sleep_time)

        # exponential backoff with max
        sleep_time = min(sleep_time * 2, max_sleep)
    if not complete:
        raise exceptions.ChangesetDidNotStabilize(change_set_id)
    return response


def create_change_set(cfn_client, fqn, template, parameters, tags,
                      replacements_only=False):
    logger.debug("Attempting to create change set for stack: %s.", fqn)
    args = {'StackName': fqn,
            'Parameters': parameters,
            'Tags': tags,
            'Capabilities': ["CAPABILITY_NAMED_IAM"],
            'ChangeSetName': get_change_set_name()}
    try:
        response = retry_on_throttling(
            cfn_client.create_change_set,
            kwargs=dict(args, **template_args(template))
        )
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == ('TemplateURL must reference '
                                              'a valid S3 object to which '
                                              'you have access.'):
            response = s3_fallback(fqn, template.url, parameters,
                                   tags, cfn_client.create_change_set,
                                   get_change_set_name())
        else:
            raise
    change_set_id = response["Id"]
    response = wait_till_change_set_complete(
        cfn_client, change_set_id
    )
    status = response["Status"]
    if status == "FAILED":
        status_reason = response["StatusReason"]
        if "didn't contain changes" in response["StatusReason"]:
            logger.debug(
                "Stack %s did not change, not updating.",
                fqn,
            )
            raise exceptions.StackDidNotChange
        raise exceptions.UnhandledChangeSetStatus(
            fqn, change_set_id, status, status_reason
        )

    execution_status = response["ExecutionStatus"]
    if execution_status != "AVAILABLE":
        raise exceptions.UnableToExecuteChangeSet(fqn,
                                                  change_set_id,
                                                  execution_status)

    changes = response["Changes"]
    return changes, change_set_id


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

    def __init__(self, region, interactive=False, replacements_only=False,
                 **kwargs):
        self.region = region
        self._outputs = {}
        self._cloudformation = None
        self.interactive = interactive
        # replacements only is only used in interactive mode
        self.replacements_only = interactive and replacements_only
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

    def create_stack(self, fqn, template, parameters, tags, **kwargs):
        """Create a new Cloudformation stack.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when creating the stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
        """

        logger.debug("Attempting to create stack %s:.", fqn)
        logger.debug("    parameters: %s", parameters)
        logger.debug("    tags: %s", tags)
        if template.url:
            logger.debug("    template_url: %s", template.url)
        else:
            logger.debug("    no template url, uploading template "
                         "directly.")
        args = dict(StackName=fqn,
                    Parameters=parameters,
                    Tags=tags,
                    Capabilities=["CAPABILITY_NAMED_IAM"])
        try:
            retry_on_throttling(
                self.cloudformation.create_stack,
                kwargs=dict(args, **template_args(template)),
            )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Message'] == ('TemplateURL must reference '
                                                  'a valid S3 object to which '
                                                  'you have access.'):
                s3_fallback(fqn, template.url, parameters, tags,
                            self.cloudformation.create_stack)
            else:
                raise

    def select_update_method(self, force_interactive):
        """Select the correct update method when updating a stack.

        Args:
            force_interactive (str): Whether or not to force interactive mode
                no matter what mode the provider is in.

        Returns:
            function: The correct object method to use when updating.
        """
        if self.interactive or force_interactive:
            return self.interactive_update_stack
        else:
            return self.default_update_stack

    def update_stack(self, fqn, template, old_parameters, parameters, tags,
                     force_interactive=False, **kwargs):
        """Update a Cloudformation stack.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when updating the stack.
            old_parameters (list): A list of dictionaries that defines the
                parameter list on the existing Cloudformation stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
            force_interactive (bool): A flag that indicates whether the update
                should be interactive. If set to True, interactive mode will
                be used no matter if the provider is in interactive mode or
                not. False will follow the behavior of the provider.
        """
        logger.debug("Attempting to update stack %s:", fqn)
        logger.debug("    parameters: %s", parameters)
        logger.debug("    tags: %s", tags)
        if template.url:
            logger.debug("    template_url: %s", template.url)
        else:
            logger.debug("    no template url, uploading template directly.")
        update_method = self.select_update_method(force_interactive)

        return update_method(fqn, template, old_parameters, parameters, tags,
                             **kwargs)

    def interactive_update_stack(self, fqn, template, old_parameters,
                                 parameters, tags, **kwargs):
        """Update a Cloudformation stack in interactive mode.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when updating the stack.
            old_parameters (list): A list of dictionaries that defines the
                parameter list on the existing Cloudformation stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
        """
        logger.debug("Using interactive provider mode for %s.", fqn)
        changes, change_set_id = create_change_set(self.cloudformation, fqn,
                                                   template, parameters,
                                                   tags, **kwargs)
        params_diff = diff_parameters(
            self.params_as_dict(old_parameters),
            self.params_as_dict(parameters))

        action = "replacements" if self.replacements_only else "changes"
        full_changeset = changes
        if self.replacements_only:
            changes = requires_replacement(changes)

        if changes or params_diff:
            output_summary(fqn, action, changes, params_diff,
                           replacements_only=self.replacements_only)
            ask_for_approval(
                full_changeset=full_changeset,
                params_diff=params_diff,
                include_verbose=True,
            )

        retry_on_throttling(
            self.cloudformation.execute_change_set,
            kwargs={
                'ChangeSetName': change_set_id,
            },
        )

    def default_update_stack(self, fqn, template, old_parameters, parameters,
                             tags, **kwargs):
        """Update a Cloudformation stack in default mode.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when updating the stack.
            old_parameters (list): A list of dictionaries that defines the
                parameter list on the existing Cloudformation stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
        """

        logger.debug("Using default provider mode for %s.", fqn)
        args = dict(StackName=fqn,
                    Parameters=parameters,
                    Tags=tags,
                    Capabilities=["CAPABILITY_NAMED_IAM"])
        try:
            retry_on_throttling(
                self.cloudformation.update_stack,
                kwargs=dict(args, **template_args(template)),
            )
        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed." in e.message:
                logger.debug(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            elif e.response['Error']['Message'] == ('TemplateURL must '
                                                    'reference a valid '
                                                    'S3 object to which '
                                                    'you have access.'):
                s3_fallback(fqn, template.url, parameters, tags,
                            self.cloudformation.update_stack)
            else:
                raise

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
        stack = self.get_stack(stack_name)

        try:
            template = retry_on_throttling(
                self.cloudformation.get_template,
                kwargs=dict(StackName=stack_name))['TemplateBody']
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

        parameters = self.params_as_dict(stack.get('Parameters', []))

        return [json.dumps(template), parameters]

    @staticmethod
    def params_as_dict(parameters_list):
        parameters = dict()
        for p in parameters_list:
            parameters[p['ParameterKey']] = p['ParameterValue']
        return parameters
