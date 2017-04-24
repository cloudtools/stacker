import logging
import time

import yaml

from ... import exceptions
from .default import (
    Provider as AWSProvider,
    retry_on_throttling,
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


def ask_for_approval(full_changeset=None, include_verbose=False):
    """Prompt the user for approval to execute a change set.

    Args:
        full_changeset (list, optional): A list of the full changeset that will
            be output if the user specifies verbose.
        include_verbose (bool, optional): Boolean for whether or not to include
            the verbose option

    """
    approval_options = ['y', 'n']
    if include_verbose:
        approval_options.append('v')

    approve = get_raw_input("Execute the above changes? [{}] ".format(
        '/'.join(approval_options)))

    if include_verbose and approve == "v":
        logger.info(
            "Full changeset:\n%s",
            yaml.safe_dump(full_changeset),
        )
        return ask_for_approval()
    elif approve != "y":
        raise exceptions.CancelExecution


def output_summary(fqn, action, changeset, replacements_only=False):
    """Log a summary of the changeset.

    Args:
        fqn (string): fully qualified name of the stack
        action (string): action to include in the log message
        changeset (list): AWS changeset
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
    if replacements:
        if not replacements_only:
            summary += 'Replacements:\n'
        summary += '\n'.join(replacements)
    if changes:
        if summary:
            summary += '\n'
        summary += 'Changes:\n%s' % ('\n'.join(changes))
    logger.info('%s %s:\n%s', fqn, action, summary)


def wait_till_change_set_complete(cfn_client, change_set_id, try_count=5,
                                  sleep_time=.1):
    """ Checks state of a changeset, returning when it is in a complete state.

    Since changesets can take a little bit of time to get into a complete
    state, we need to poll it until it does so. This will try to get the
    state 5 times, waiting `sleep_time` seconds between each try. If, after
    that time, the changeset is not in a complete state it fails.

    Args:
        cfn_client (:class:`botocore.client.CloudFormation`): Used to query
            cloudformation.
        change_set_id (str): The unique changeset id to wait for.
        try_count (int): Number of times to try the call.
        sleep_time (int): Time to sleep between attempts.

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
        time.sleep(sleep_time)
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
        cfn_client, change_set_id, sleep_time=2
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

    def update_stack(self, fqn, template_url, parameters, tags, diff=False,
                     **kwargs):
        changes, change_set_id = create_change_set(self.cloudformation, fqn,
                                                   template_url, parameters,
                                                   tags, **kwargs)

        action = "replacements" if self.replacements_only else "changes"
        full_changes = changes
        if self.replacements_only:
            changes = requires_replacement(changes)

        if changes:
            output_summary(fqn, action, changes,
                           replacements_only=self.replacements_only)
            if not diff:
                ask_for_approval(
                    full_changes=full_changes,
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
