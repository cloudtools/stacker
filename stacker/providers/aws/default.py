import json
import yaml
import logging
import time
import urllib.parse
import sys

# thread safe, memoized, provider builder.
from threading import Lock

import botocore.exceptions
from botocore.config import Config

from ..base import BaseProvider
from ... import exceptions
from ...ui import ui
from ...util import parse_cloudformation_template
from stacker.session_cache import get_session

from ...actions.diff import (
    DictValue,
    diff_parameters,
    format_params_diff as format_diff
)

logger = logging.getLogger(__name__)

# This value controls the maximum number of times a CloudFormation API call
# will be attempted, after being throttled. This value is used in an
# exponential backoff algorithm to determine how long the client should wait
# until attempting a retry:
#
#   base * growth_factor ^ (attempts - 1)
#
# A value of 10 here would cause the worst case wait time for the last retry to
# be ~8 mins:
#
#   1 * 2 ^ (10 - 1) = 512 seconds
#
# References:
# https://github.com/boto/botocore/blob/1.6.1/botocore/retryhandler.py#L39-L58
# https://github.com/boto/botocore/blob/1.6.1/botocore/data/_retry.json#L97-L121
MAX_ATTEMPTS = 10

# Updated this to 15 retries with a 1 second sleep between retries. This is
# only used when a call to `get_events` fails due to the stack not being
# found. This is often the case because Cloudformation is taking too long
# to create the stack. 15 seconds should, hopefully, be plenty of time for
# the stack to start showing up in the API.
MAX_TAIL_RETRIES = 15
TAIL_RETRY_SLEEP = 1
GET_EVENTS_SLEEP = 1
DEFAULT_CAPABILITIES = ["CAPABILITY_NAMED_IAM",
                        "CAPABILITY_AUTO_EXPAND"]


def get_cloudformation_client(session):
    config = Config(
        retries=dict(
            max_attempts=MAX_ATTEMPTS
        )
    )
    return session.client('cloudformation', config=config)


def get_output_dict(stack):
    """Returns a dict of key/values for the outputs for a given CF stack.

    Args:
        stack (dict): The stack object to get
            outputs from.

    Returns:
        dict: A dictionary with key/values for each output on the stack.

    """
    outputs = {}
    if 'Outputs' not in stack:
        return outputs

    for output in stack['Outputs']:
        logger.debug("    %s %s: %s", stack['StackName'], output['OutputKey'],
                     output['OutputValue'])
        outputs[output['OutputKey']] = output['OutputValue']
    return outputs


def s3_fallback(fqn, template, parameters, tags, method,
                change_set_name=None, service_role=None):
    logger.warn("DEPRECATION WARNING: Falling back to legacy "
                "stacker S3 bucket region for templates. See "
                "http://stacker.readthedocs.io/en/latest/config.html#s3-bucket"
                " for more information.")
    # extra line break on purpose to avoid status updates removing URL
    # from view
    logger.warn("\n")
    logger.debug("Modifying the S3 TemplateURL to point to "
                 "us-east-1 endpoint")
    template_url = template.url
    template_url_parsed = urllib.parse.urlparse(template_url)
    template_url_parsed = template_url_parsed._replace(
        netloc="s3.amazonaws.com")
    template_url = urllib.parse.urlunparse(template_url_parsed)
    logger.debug("Using template_url: %s", template_url)
    args = generate_cloudformation_args(
        fqn, parameters, tags, template,
        service_role=service_role,
        change_set_name=get_change_set_name()
    )

    response = method(**args)
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


def output_full_changeset(full_changeset=None, params_diff=None,
                          answer=None, fqn=None):
    """Optionally output full changeset.

    Args:
        full_changeset (list, optional): A list of the full changeset that will
            be output if the user specifies verbose.
        params_diff (list, optional): A list of DictValue detailing the
            differences between two parameters returned by
            :func:`stacker.actions.diff.diff_dictionaries`
        answer (str, optional): predetermined answer to the prompt if it has
            already been answered or inferred.
        fqn (str, optional): fully qualified name of the stack.

    """
    if not answer:
        answer = ui.ask('Show full change set? [y/n] ').lower()
    if answer == 'n':
        return
    if answer in ['y', 'v']:
        if fqn:
            msg = '%s full changeset' % (fqn)
        else:
            msg = 'Full changeset'
        if params_diff:
            logger.info(
                "%s:\n\n%s\n%s",
                msg,
                format_params_diff(params_diff),
                yaml.safe_dump(full_changeset),
            )
        else:
            logger.info(
                "%s:\n%s",
                msg,
                yaml.safe_dump(full_changeset),
            )
        return
    raise exceptions.CancelExecution


def ask_for_approval(full_changeset=None, params_diff=None,
                     include_verbose=False, fqn=None):
    """Prompt the user for approval to execute a change set.

    Args:
        full_changeset (list, optional): A list of the full changeset that will
            be output if the user specifies verbose.
        params_diff (list, optional): A list of DictValue detailing the
            differences between two parameters returned by
            :func:`stacker.actions.diff.diff_dictionaries`
        include_verbose (bool, optional): Boolean for whether or not to include
            the verbose option.
        fqn (str): fully qualified name of the stack.

    """
    approval_options = ['y', 'n']
    if include_verbose:
        approval_options.append('v')

    approve = ui.ask("Execute the above changes? [{}] ".format(
        '/'.join(approval_options))).lower()

    if include_verbose and approve == "v":
        output_full_changeset(full_changeset=full_changeset,
                              params_diff=params_diff, answer=approve, fqn=fqn)
        return ask_for_approval(fqn=fqn)
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
        response = cfn_client.describe_change_set(
            ChangeSetName=change_set_id,
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


def create_change_set(
    cfn_client,
    fqn,
    template,
    parameters,
    tags,
    change_set_type='UPDATE',
    replacements_only=False,
    service_role=None,
    notification_arns=None
):
    logger.debug("Attempting to create change set of type %s for stack: %s.",
                 change_set_type,
                 fqn)
    args = generate_cloudformation_args(
        fqn, parameters, tags, template,
        change_set_type=change_set_type,
        service_role=service_role,
        change_set_name=get_change_set_name(),
        notification_arns=notification_arns
    )
    try:
        response = cfn_client.create_change_set(**args)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == ('TemplateURL must reference '
                                              'a valid S3 object to which '
                                              'you have access.'):
            response = s3_fallback(fqn, template, parameters,
                                   tags, cfn_client.create_change_set,
                                   get_change_set_name(),
                                   service_role)
        else:
            raise
    change_set_id = response["Id"]
    response = wait_till_change_set_complete(
        cfn_client, change_set_id
    )
    status = response["Status"]
    if status == "FAILED":
        status_reason = response["StatusReason"]
        if ("didn't contain changes" in response["StatusReason"] or
                "No updates are to be performed" in response["StatusReason"]):
            logger.debug(
                "Stack %s did not change, not updating and removing "
                "changeset.",
                fqn,
            )
            cfn_client.delete_change_set(ChangeSetName=change_set_id)
            raise exceptions.StackDidNotChange()
        logger.warn(
            "Got strange status, '%s' for changeset '%s'. Not deleting for "
            "further investigation - you will need to delete the changeset "
            "manually.",
            status, change_set_id
        )
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


def check_tags_contain(actual, expected):
    """Check if a set of AWS resource tags is contained in another

    Every tag key in `expected` must be present in `actual`, and have the same
    value. Extra keys in `actual` but not in `expected` are ignored.

    Args:
        actual (list): Set of tags to be verified, usually from the description
            of a resource. Each item must be a `dict` containing `Key` and
            `Value` items.
        expected (list): Set of tags that must be present in `actual` (in the
            same format).
    """

    actual_set = set((item["Key"], item["Value"]) for item in actual)
    expected_set = set((item["Key"], item["Value"]) for item in expected)

    return actual_set >= expected_set


def generate_cloudformation_args(
    stack_name,
    parameters,
    tags,
    template,
    capabilities=DEFAULT_CAPABILITIES,
    change_set_type=None,
    service_role=None,
    stack_policy=None,
    change_set_name=None,
    notification_arns=None,
):
    """Used to generate the args for common cloudformation API interactions.

    This is used for create_stack/update_stack/create_change_set calls in
    cloudformation.

    Args:
        stack_name (str): The fully qualified stack name in Cloudformation.
        parameters (list): A list of dictionaries that defines the
            parameter list to be applied to the Cloudformation stack.
        tags (list): A list of dictionaries that defines the tags
            that should be applied to the Cloudformation stack.
        template (:class:`stacker.provider.base.Template`): The template
            object.
        capabilities (list, optional): A list of capabilities to use when
            updating Cloudformation.
        change_set_type (str, optional): An optional change set type to use
            with create_change_set.
        service_role (str, optional): An optional service role to use when
            interacting with Cloudformation.
        stack_policy (:class:`stacker.providers.base.Template`): A template
            object representing a stack policy.
        change_set_name (str, optional): An optional change set name to use
            with create_change_set.
        notification_arns (list, optional): An optional list of SNS topic ARNs
            to send CloudFormation Events to.

    Returns:
        dict: A dictionary of arguments to be used in the Cloudformation API
            call.
    """
    args = {
        "StackName": stack_name,
        "Parameters": parameters,
        "Tags": tags,
        "Capabilities": capabilities,
    }

    if service_role:
        args["RoleARN"] = service_role

    if change_set_name:
        args["ChangeSetName"] = change_set_name

    if notification_arns:
        args["NotificationARNs"] = notification_arns

    if change_set_type:
        args["ChangeSetType"] = change_set_type

    if template.url:
        args["TemplateURL"] = template.url
    else:
        args["TemplateBody"] = template.body

    # When creating args for CreateChangeSet, don't include the stack policy,
    # since ChangeSets don't support it.
    if not change_set_name:
        args.update(generate_stack_policy_args(stack_policy))

    return args


def generate_stack_policy_args(stack_policy=None):
    """ Converts a stack policy object into keyword args.

    Args:
        stack_policy (:class:`stacker.providers.base.Template`): A template
            object representing a stack policy.

    Returns:
        dict: A dictionary of keyword arguments to be used elsewhere.
    """

    args = {}
    if stack_policy:
        logger.debug("Stack has a stack policy")
        if stack_policy.url:
            # stacker currently does not support uploading stack policies to
            # S3, so this will never get hit (unless your implementing S3
            # uploads, and then you're probably reading this comment about why
            # the exception below was raised :))
            #
            # args["StackPolicyURL"] = stack_policy.url
            raise NotImplementedError
        else:
            args["StackPolicyBody"] = stack_policy.body
    return args


class ProviderBuilder(object):
    """Implements a Memoized ProviderBuilder for the AWS provider."""

    def __init__(self, region=None, **kwargs):
        self.region = region
        self.kwargs = kwargs
        self.providers = {}
        self.lock = Lock()

    def build(self, region=None, profile=None):
        """Get or create the provider for the given region and profile."""

        with self.lock:
            # memoization lookup key derived from region + profile.
            key = "{}-{}".format(profile, region)
            try:
                # assume provider is in provider dictionary.
                provider = self.providers[key]
            except KeyError:
                msg = "Missed memoized lookup ({}), creating new AWS Provider."
                logger.debug(msg.format(key))
                if not region:
                    region = self.region
                # memoize the result for later.
                self.providers[key] = Provider(
                    get_session(region=region, profile=profile),
                    region=region,
                    **self.kwargs
                )
                provider = self.providers[key]

        return provider


class Provider(BaseProvider):

    """AWS CloudFormation Provider"""

    DELETED_STATUS = "DELETE_COMPLETE"

    IN_PROGRESS_STATUSES = (
        "CREATE_IN_PROGRESS",
        "IMPORT_IN_PROGRESS",
        "UPDATE_IN_PROGRESS",
        "DELETE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    )

    ROLLING_BACK_STATUSES = (
        "ROLLBACK_IN_PROGRESS",
        "IMPORT_ROLLBACK_IN_PROGRESS",
        "UPDATE_ROLLBACK_IN_PROGRESS"
    )

    FAILED_STATUSES = (
        "CREATE_FAILED",
        "ROLLBACK_FAILED",
        "ROLLBACK_COMPLETE",
        "DELETE_FAILED",
        "IMPORT_ROLLBACK_FAILED",
        "UPDATE_ROLLBACK_FAILED",
        # Note: UPDATE_ROLLBACK_COMPLETE is in both the FAILED and COMPLETE
        # sets, because we need to wait for it when a rollback is triggered,
        # but still mark the stack as failed.
        "UPDATE_ROLLBACK_COMPLETE",
    )

    COMPLETE_STATUSES = (
        "CREATE_COMPLETE",
        "DELETE_COMPLETE",
        "IMPORT_COMPLETE",
        "UPDATE_COMPLETE",
        "IMPORT_ROLLBACK_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    )

    RECREATION_STATUSES = (
        "CREATE_FAILED",
        "ROLLBACK_FAILED",
        "ROLLBACK_COMPLETE"
    )

    REVIEW_STATUS = "REVIEW_IN_PROGRESS"

    def __init__(self, session, region=None, interactive=False,
                 replacements_only=False, recreate_failed=False,
                 service_role=None, **kwargs):
        self._outputs = {}
        self.region = region
        self.cloudformation = get_cloudformation_client(session)
        self.interactive = interactive
        # replacements only is only used in interactive mode
        self.replacements_only = interactive and replacements_only
        self.recreate_failed = interactive or recreate_failed
        self.service_role = service_role

    def get_stack(self, stack_name, **kwargs):
        try:
            return self.cloudformation.describe_stacks(
                StackName=stack_name)['Stacks'][0]
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in str(e):
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

    def is_stack_recreatable(self, stack, **kwargs):
        return self.get_stack_status(stack) in self.RECREATION_STATUSES

    def is_stack_rolling_back(self, stack, **kwargs):
        return self.get_stack_status(stack) in self.ROLLING_BACK_STATUSES

    def is_stack_failed(self, stack, **kwargs):
        return self.get_stack_status(stack) in self.FAILED_STATUSES

    def is_stack_in_review(self, stack, **kwargs):
        return self.get_stack_status(stack) == self.REVIEW_STATUS

    def tail_stack(self, stack, cancel, log_func=None, **kwargs):
        def _log_func(e):
            event_args = [e['ResourceStatus'], e['ResourceType'],
                          e.get('ResourceStatusReason', None)]
            # filter out any values that are empty
            event_args = [arg for arg in event_args if arg]
            template = " ".join(["[%s]"] + ["%s" for _ in event_args])
            logger.info(template, *([stack.fqn] + event_args))

        log_func = log_func or _log_func

        logger.info("Tailing stack: %s", stack.fqn)

        attempts = 0
        while True:
            attempts += 1
            try:
                self.tail(stack.fqn, cancel=cancel, log_func=log_func,
                          include_initial=False)
                break
            except botocore.exceptions.ClientError as e:
                if "does not exist" in str(e) and attempts < MAX_TAIL_RETRIES:
                    # stack might be in the process of launching, wait for a
                    # second and try again
                    if cancel.wait(TAIL_RETRY_SLEEP):
                        return
                    continue
                else:
                    raise

    @staticmethod
    def _tail_print(e):
        print("%s %s %s" % (e['ResourceStatus'],
                            e['ResourceType'],
                            e['EventId']))

    def get_events(self, stack_name, chronological=True):
        """Get the events in batches and return in chronological order"""
        next_token = None
        event_list = []
        while True:
            if next_token is not None:
                events = self.cloudformation.describe_stack_events(
                    StackName=stack_name, NextToken=next_token
                )
            else:
                events = self.cloudformation.describe_stack_events(
                    StackName=stack_name
                )
            event_list.append(events['StackEvents'])
            next_token = events.get('NextToken', None)
            if next_token is None:
                break
            time.sleep(GET_EVENTS_SLEEP)
        if chronological:
            return reversed(sum(event_list, []))
        else:
            return sum(event_list, [])

    def get_rollback_status_reason(self, stack_name):
        """Process events and returns latest roll back reason"""
        event = next((item for item in self.get_events(stack_name,
                      False) if item["ResourceStatus"] ==
                      "UPDATE_ROLLBACK_IN_PROGRESS"), None)
        if event:
            reason = event["ResourceStatusReason"]
            return reason
        else:
            event = next((item for item in self.get_events(stack_name)
                          if item["ResourceStatus"] ==
                          "ROLLBACK_IN_PROGRESS"), None)
            reason = event["ResourceStatusReason"]
            return reason

    def tail(self, stack_name, cancel, log_func=_tail_print, sleep_time=5,
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
        while True:
            events = self.get_events(stack_name)
            for e in events:
                if e['EventId'] not in seen:
                    log_func(e)
                    seen.add(e['EventId'])
            if cancel.wait(sleep_time):
                return

    def destroy_stack(self, stack, **kwargs):
        logger.debug("Destroying stack: %s" % (self.get_stack_name(stack)))
        args = {"StackName": self.get_stack_name(stack)}
        if self.service_role:
            args["RoleARN"] = self.service_role

        self.cloudformation.delete_stack(**args)
        return True

    def create_stack(
        self, fqn, template, parameters, tags,
        force_change_set=False,
        stack_policy=None,
        notification_arns=None,
        **kwargs
    ):
        """Create a new Cloudformation stack.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when creating the stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
            force_change_set (bool): Whether or not to force change set use.
            stack_policy (:class:`stacker.providers.base.Template`): A template
                object representing a stack policy.
            notification_arns (list, optional): An optional list of SNS topic
                ARNs to send CloudFormation Events to.
        """

        logger.debug("Attempting to create stack %s:.", fqn)
        logger.debug("    parameters: %s", parameters)
        logger.debug("    tags: %s", tags)
        if template.url:
            logger.debug("    template_url: %s", template.url)
        else:
            logger.debug("    no template url, uploading template "
                         "directly.")
        if force_change_set:
            logger.debug("force_change_set set to True, creating stack with "
                         "changeset.")
            _changes, change_set_id = create_change_set(
                self.cloudformation, fqn, template, parameters, tags,
                'CREATE', service_role=self.service_role, **kwargs
            )

            self.cloudformation.execute_change_set(
                ChangeSetName=change_set_id,
            )
        else:
            args = generate_cloudformation_args(
                fqn, parameters, tags, template,
                service_role=self.service_role,
                stack_policy=stack_policy,
                notification_arns=notification_arns
            )

            try:
                self.cloudformation.create_stack(**args)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Message'] == ('TemplateURL must '
                                                      'reference a valid S3 '
                                                      'object to which you '
                                                      'have access.'):
                    s3_fallback(fqn, template, parameters, tags,
                                self.cloudformation.create_stack,
                                self.service_role)
                else:
                    raise

    def select_update_method(self, force_interactive, force_change_set):
        """Select the correct update method when updating a stack.

        Args:
            force_interactive (str): Whether or not to force interactive mode
                no matter what mode the provider is in.
            force_change_set (bool): Whether or not to force change set use.

        Returns:
            function: The correct object method to use when updating.
        """
        if self.interactive or force_interactive:
            return self.interactive_update_stack
        elif force_change_set:
            return self.noninteractive_changeset_update
        else:
            return self.default_update_stack

    def prepare_stack_for_update(self, stack, tags):
        """Prepare a stack for updating

        It may involve deleting the stack if is has failed it's initial
        creation. The deletion is only allowed if:
          - The stack contains all the tags configured in the current context;
          - The stack is in one of the statuses considered safe to re-create
          - ``recreate_failed`` is enabled, due to either being explicitly
            enabled by the user, or because interactive mode is on.

        Args:
            stack (dict): a stack object returned from get_stack
            tags (list): list of expected tags that must be present in the
                stack if it must be re-created

        Returns:
            bool: True if the stack can be updated, False if it must be
                re-created
        """

        if self.is_stack_destroyed(stack):
            return False
        elif self.is_stack_completed(stack):
            return True

        stack_name = self.get_stack_name(stack)
        stack_status = self.get_stack_status(stack)

        if self.is_stack_in_progress(stack):
            raise exceptions.StackUpdateBadStatus(
                stack_name, stack_status,
                'Update already in-progress')

        if not self.is_stack_recreatable(stack):
            raise exceptions.StackUpdateBadStatus(
                stack_name, stack_status,
                'Unsupported state for re-creation')

        if not self.recreate_failed:
            raise exceptions.StackUpdateBadStatus(
                stack_name, stack_status,
                'Stack re-creation is disabled. Run stacker again with the '
                '--recreate-failed option to force it to be deleted and '
                'created from scratch.')

        stack_tags = self.get_stack_tags(stack)
        if not check_tags_contain(stack_tags, tags):
            raise exceptions.StackUpdateBadStatus(
                stack_name, stack_status,
                'Tags differ from current configuration, possibly not created '
                'with stacker')

        if self.interactive:
            sys.stdout.write(
                'The \"%s\" stack is in a failed state (%s).\n'
                'It cannot be updated, but it can be deleted and re-created.\n'
                'All its current resources will IRREVERSIBLY DESTROYED.\n'
                'Proceed carefully!\n\n' % (stack_name, stack_status))
            sys.stdout.flush()

            ask_for_approval(include_verbose=False, fqn=stack_name)

        logger.warn('Destroying stack \"%s\" for re-creation', stack_name)
        self.destroy_stack(stack)

        return False

    def update_stack(self, fqn, template, old_parameters, parameters, tags,
                     force_interactive=False, force_change_set=False,
                     stack_policy=None, **kwargs):
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
            force_change_set (bool): A flag that indicates whether the update
                must be executed with a change set.
            stack_policy (:class:`stacker.providers.base.Template`): A template
                object representing a stack policy.
        """
        logger.debug("Attempting to update stack %s:", fqn)
        logger.debug("    parameters: %s", parameters)
        logger.debug("    tags: %s", tags)
        if template.url:
            logger.debug("    template_url: %s", template.url)
        else:
            logger.debug("    no template url, uploading template directly.")
        update_method = self.select_update_method(force_interactive,
                                                  force_change_set)

        return update_method(fqn, template, old_parameters, parameters,
                             stack_policy=stack_policy, tags=tags, **kwargs)

    def deal_with_changeset_stack_policy(self, fqn, stack_policy):
        """ Set a stack policy when using changesets.

        ChangeSets don't allow you to set stack policies in the same call to
        update them. This sets it before executing the changeset if the
        stack policy is passed in.

        Args:
            stack_policy (:class:`stacker.providers.base.Template`): A template
                object representing a stack policy.
        """
        if stack_policy:
            kwargs = generate_stack_policy_args(stack_policy)
            kwargs["StackName"] = fqn
            logger.debug("Setting stack policy on %s.", fqn)
            self.cloudformation.set_stack_policy(**kwargs)

    def interactive_update_stack(self, fqn, template, old_parameters,
                                 parameters, stack_policy, tags,
                                 **kwargs):
        """Update a Cloudformation stack in interactive mode.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when updating the stack.
            old_parameters (list): A list of dictionaries that defines the
                parameter list on the existing Cloudformation stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            stack_policy (:class:`stacker.providers.base.Template`): A template
                object representing a stack policy.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
        """
        logger.debug("Using interactive provider mode for %s.", fqn)
        changes, change_set_id = create_change_set(
            self.cloudformation, fqn, template, parameters, tags,
            'UPDATE', service_role=self.service_role, **kwargs
        )
        old_parameters_as_dict = self.params_as_dict(old_parameters)
        new_parameters_as_dict = self.params_as_dict(
            [x
             if 'ParameterValue' in x
             else {'ParameterKey': x['ParameterKey'],
                   'ParameterValue': old_parameters_as_dict[x['ParameterKey']]}
             for x in parameters]
        )
        params_diff = diff_parameters(
            old_parameters_as_dict,
            new_parameters_as_dict)

        action = "replacements" if self.replacements_only else "changes"
        full_changeset = changes
        if self.replacements_only:
            changes = requires_replacement(changes)

        if changes or params_diff:
            ui.lock()
            try:
                output_summary(fqn, action, changes, params_diff,
                               replacements_only=self.replacements_only)
                ask_for_approval(
                    full_changeset=full_changeset,
                    params_diff=params_diff,
                    include_verbose=True,
                    fqn=fqn,
                )
            finally:
                ui.unlock()

        self.deal_with_changeset_stack_policy(fqn, stack_policy)

        self.cloudformation.execute_change_set(
            ChangeSetName=change_set_id,
        )

    def noninteractive_changeset_update(self, fqn, template, old_parameters,
                                        parameters, stack_policy, tags,
                                        **kwargs):
        """Update a Cloudformation stack using a change set.

        This is required for stacks with a defined Transform (i.e. SAM), as the
        default update_stack API cannot be used with them.

        Args:
            fqn (str): The fully qualified name of the Cloudformation stack.
            template (:class:`stacker.providers.base.Template`): A Template
                object to use when updating the stack.
            old_parameters (list): A list of dictionaries that defines the
                parameter list on the existing Cloudformation stack.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            stack_policy (:class:`stacker.providers.base.Template`): A template
                object representing a stack policy.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.
        """
        logger.debug("Using noninterative changeset provider mode "
                     "for %s.", fqn)
        _changes, change_set_id = create_change_set(
            self.cloudformation, fqn, template, parameters, tags,
            'UPDATE', service_role=self.service_role, **kwargs
        )

        self.deal_with_changeset_stack_policy(fqn, stack_policy)

        self.cloudformation.execute_change_set(
            ChangeSetName=change_set_id,
        )

    def default_update_stack(self, fqn, template, old_parameters, parameters,
                             tags, stack_policy=None,
                             notification_arns=[], **kwargs):
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
            stack_policy (:class:`stacker.providers.base.Template`): A template
                object representing a stack policy.
        """

        logger.debug("Using default provider mode for %s.", fqn)
        args = generate_cloudformation_args(
            fqn, parameters, tags, template,
            service_role=self.service_role,
            stack_policy=stack_policy,
            notification_arns=notification_arns
        )

        try:
            self.cloudformation.update_stack(**args)
        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed." in str(e):
                logger.debug(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            elif e.response['Error']['Message'] == ('TemplateURL must '
                                                    'reference a valid '
                                                    'S3 object to which '
                                                    'you have access.'):
                s3_fallback(fqn, template, parameters, tags,
                            self.cloudformation.update_stack,
                            self.service_role)
            else:
                raise

    def get_stack_name(self, stack, **kwargs):
        return stack['StackName']

    def get_stack_tags(self, stack, **kwargs):
        return stack['Tags']

    def get_outputs(self, stack_name, *args, **kwargs):
        if stack_name not in self._outputs:
            stack = self.get_stack(stack_name)
            self._outputs[stack_name] = get_output_dict(stack)
        return self._outputs[stack_name]

    def get_output_dict(self, stack):
        return get_output_dict(stack)

    def get_stack_info(self, stack):
        """ Get the template and parameters of the stack currently in AWS

        Returns [ template, parameters ]
        """
        stack_name = stack['StackId']

        try:
            template = self.cloudformation.get_template(
                StackName=stack_name)['TemplateBody']
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in str(e):
                raise
            raise exceptions.StackDoesNotExist(stack_name)

        parameters = self.params_as_dict(stack.get('Parameters', []))

        if isinstance(template, str):  # handle yaml templates
            template = parse_cloudformation_template(template)

        return [json.dumps(template), parameters]

    def get_stack_changes(self, stack, template, parameters,
                          tags, **kwargs):
        """Get the changes from a ChangeSet.

        Args:
            stack (:class:`stacker.stack.Stack`): the stack to get changes
            template (:class:`stacker.providers.base.Template`): A Template
                object to compaired to.
            parameters (list): A list of dictionaries that defines the
                parameter list to be applied to the Cloudformation stack.
            tags (list): A list of dictionaries that defines the tags
                that should be applied to the Cloudformation stack.

        Returns:
            dict: Stack outputs with inferred changes.

        """
        try:
            stack_details = self.get_stack(stack.fqn)
            # handling for orphaned changeset temp stacks
            if self.get_stack_status(
                    stack_details) == self.REVIEW_STATUS:
                raise exceptions.StackDoesNotExist(stack.fqn)
            _old_template, old_params = self.get_stack_info(
                stack_details
            )
            old_template = parse_cloudformation_template(_old_template)
            change_type = 'UPDATE'
        except exceptions.StackDoesNotExist:
            old_params = {}
            old_template = {}
            change_type = 'CREATE'

        changes, change_set_id = create_change_set(
            self.cloudformation, stack.fqn, template, parameters, tags,
            change_type, service_role=self.service_role, **kwargs
        )
        new_parameters_as_dict = self.params_as_dict(
            [x
             if 'ParameterValue' in x
             else {'ParameterKey': x['ParameterKey'],
                   'ParameterValue': old_params[x['ParameterKey']]}
             for x in parameters]
        )
        params_diff = diff_parameters(old_params, new_parameters_as_dict)

        if changes or params_diff:
            ui.lock()
            try:
                if self.interactive:
                    output_summary(stack.fqn, 'changes', changes,
                                   params_diff,
                                   replacements_only=self.replacements_only)
                    output_full_changeset(full_changeset=changes,
                                          params_diff=params_diff,
                                          fqn=stack.fqn)
                else:
                    output_full_changeset(full_changeset=changes,
                                          params_diff=params_diff,
                                          answer='y', fqn=stack.fqn)
            finally:
                ui.unlock()

        self.cloudformation.delete_change_set(
            ChangeSetName=change_set_id
        )

        # ensure current stack outputs are loaded
        self.get_outputs(stack.fqn)

        # infer which outputs may have changed
        refs_to_invalidate = []
        for change in changes:
            resc_change = change.get('ResourceChange', {})
            if resc_change.get('Type') == 'Add':
                continue  # we don't care about anything new
            # scope of changes that can invalidate a change
            if resc_change and (resc_change.get('Replacement') == 'True' or
                                'Properties' in resc_change['Scope']):
                logger.debug('%s added to invalidation list for %s',
                             resc_change['LogicalResourceId'], stack.fqn)
                refs_to_invalidate.append(resc_change['LogicalResourceId'])

        # invalidate cached outputs with inferred changes
        for output, props in old_template.get('Outputs', {}).items():
            if any(r in str(props['Value']) for r in refs_to_invalidate):
                self._outputs[stack.fqn].pop(output)
                logger.debug('Removed %s from the outputs of %s',
                             output, stack.fqn)

        # push values for new + invalidated outputs to outputs
        for output_name, output_params in \
                stack.blueprint.get_output_definitions().items():
            if output_name not in self._outputs[stack.fqn]:
                self._outputs[stack.fqn][output_name] = (
                    '<inferred-change: {}.{}={}>'.format(
                        stack.fqn, output_name,
                        str(output_params['Value'])
                    )
                )

        # when creating a changeset for a new stack, CFN creates a temporary
        # stack with a status of REVIEW_IN_PROGRESS. this is only removed if
        # the changeset is executed or it is manually deleted.
        if change_type == 'CREATE':
            try:
                temp_stack = self.get_stack(stack.fqn)
                if self.is_stack_in_review(temp_stack):
                    logger.debug('Removing temporary stack that is created '
                                 'with a ChangeSet of type "CREATE"')
                    self.destroy_stack(temp_stack)
            except exceptions.StackDoesNotExist:
                # not an issue if the stack was already cleaned up
                logger.debug('Stack does not exist: %s', stack.fqn)

        return self.get_outputs(stack.fqn)

    @staticmethod
    def params_as_dict(parameters_list):
        parameters = dict()
        for p in parameters_list:
            parameters[p['ParameterKey']] = p['ParameterValue']
        return parameters
