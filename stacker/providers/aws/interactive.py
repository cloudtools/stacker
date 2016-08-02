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
        changeset (List): List of changes

    Returns:
        List: A list of changes that require replacement, if any.

    """
    return [r for r in changeset if r["ResourceChange"]["Replacement"] ==
            'True']


def ask_for_approval(full_changeset=None, include_verbose=False):
    approval_options = ['y', 'n']
    if include_verbose:
        approval_options.append('v')

    approve = raw_input("Execute the above changes? [{}] ".format(
        '/'.join(approval_options)))

    if include_verbose and approve == "v":
        logger.info(
            "Full changeset:\n%s",
            yaml.safe_dump(full_changeset),
        )
        return ask_for_approval()
    elif approve != "y":
        raise exceptions.CancelExecution


def output_summary(fqn, action, changeset):
    replacements = []
    changes = []
    for change in changeset:
        resource = change['ResourceChange']
        replacement = resource['Replacement'] == 'True'
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
        summary = 'Replacements:\n%s' % ('\n'.join(replacements))
    if changes:
        if summary:
            summary += '\n'
        summary += 'Changes:\n%s' % ('\n'.join(changes))
    logger.info('%s %s:\n%s\n', fqn, action, summary)


class Provider(AWSProvider):
    """AWS Cloudformation Change Set Provider"""

    def __init__(self, *args, **kwargs):
        strict = kwargs.pop('strict', False)
        super(Provider, self).__init__(*args, **kwargs)
        self.strict = strict

    def _wait_till_change_set_complete(self, change_set_id):
        complete = False
        response = None
        while not complete:
            response = retry_on_throttling(
                self.cloudformation.describe_change_set,
                kwargs={
                    'ChangeSetName': change_set_id,
                },
            )
            complete = response["Status"] in ("FAILED", "CREATE_COMPLETE")
            if not complete:
                time.sleep(2)
        return response

    def update_stack(self, fqn, template_url, parameters, tags, **kwargs):
        logger.debug("Attempting to create change set for stack: %s.", fqn)
        response = retry_on_throttling(
            self.cloudformation.create_change_set,
            kwargs={
                'StackName': fqn,
                'TemplateURL': template_url,
                'Parameters': parameters,
                'Tags': tags,
                'Capabilities': ["CAPABILITY_IAM"],
                'ChangeSetName': get_change_set_name(),
            },
        )
        change_set_id = response["Id"]
        response = self._wait_till_change_set_complete(change_set_id)
        if response["Status"] == "FAILED":
            if "didn't contain changes" in response["StatusReason"]:
                logger.debug(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            raise Exception(
                "Failed to describe change set: {}".format(response)
            )

        if response["ExecutionStatus"] != "AVAILABLE":
            raise Exception("Unable to execute change set: {}".format(response))

        action = "changes" if self.strict else "replacements"
        changeset = response["Changes"]
        if not self.strict:
            changeset = requires_replacement(changeset)

        if len(changeset):
            output_summary(fqn, action, changeset)
            ask_for_approval(
                full_changeset=response["Changes"],
                include_verbose=True,
            )

        retry_on_throttling(
            self.cloudformation.execute_change_set,
            kwargs={
                'ChangeSetName': change_set_id,
            },
        )
        return True
