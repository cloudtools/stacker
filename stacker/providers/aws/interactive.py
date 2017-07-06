import logging
import time

import yaml

from .default import (
    Provider as AWSProvider,
    retry_on_throttling,
)
from ... import exceptions
from ...actions.diff import (
    DictValue,
    diff_parameters,
    format_params_diff as format_diff
)

logger = logging.getLogger(__name__)


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
    return [r for r in changeset if r["ResourceChange"]["Replacement"] ==
            'True']


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


def create_change_set(cfn_client, fqn, template_url, parameters, tags,
                      replacements_only=False):
    logger.debug("Attempting to create change set for stack: %s.", fqn)
    response = retry_on_throttling(
        cfn_client.create_change_set,
        kwargs={
            'StackName': fqn,
            'TemplateURL': template_url,
            'Parameters': parameters,
            'Tags': tags,
            'Capabilities': ["CAPABILITY_NAMED_IAM"],
            'ChangeSetName': get_change_set_name(),
        },
    )
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


class Provider(AWSProvider):
    """AWS Cloudformation Change Set Provider"""

    def __init__(self, region, replacements_only=False, *args, **kwargs):
        self.replacements_only = replacements_only
        super(Provider, self).__init__(region=region, *args, **kwargs)

    def update_stack(self, fqn, template_url, old_parameters, parameters,
                     tags, diff=False, **kwargs):
        changes, change_set_id = create_change_set(self.cloudformation, fqn,
                                                   template_url, parameters,
                                                   tags, **kwargs)
        params_diff = diff_parameters(
            AWSProvider.params_as_dict(old_parameters),
            AWSProvider.params_as_dict(parameters))

        action = "replacements" if self.replacements_only else "changes"
        full_changeset = changes
        if self.replacements_only:
            changes = requires_replacement(changes)

        if changes or params_diff:
            output_summary(fqn, action, changes, params_diff,
                           replacements_only=self.replacements_only)
            if not diff:
                ask_for_approval(
                    full_changeset=full_changeset,
                    params_diff=params_diff,
                    include_verbose=True,
                )

        if not diff:
            retry_on_throttling(
                self.cloudformation.execute_change_set,
                kwargs={
                    'ChangeSetName': change_set_id,
                },
            )
        else:
            retry_on_throttling(
                self.cloudformation.delete_change_set,
                kwargs={
                    'ChangeSetName': change_set_id,
                },
            )

        return True
