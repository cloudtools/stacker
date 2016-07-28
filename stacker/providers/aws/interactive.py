import logging
import time

import yaml

from ... import exceptions
from .default import (
    Provider as BaseProvider,
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


class Provider(BaseProvider):
    """AWS Cloudformation Change Set Provider"""

    def _wait_till_change_set_complete(self, change_set_id):
        response = retry_on_throttling(
            self.cloudformation.describe_change_set,
            kwargs={
                'ChangeSetName': change_set_id,
            },
        )
        if response["Status"] not in ("FAILED", "CREATE_COMPLETE"):
            time.sleep(2)
            return self._wait_till_change_set_complete(change_set_id)
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

        print "\nCloudformation wants to make the following changes to stack: {}\n".format(fqn)
        print yaml.safe_dump(response["Changes"])
        approve = raw_input("Execute the above changes? [y/n] ")
        if approve != "y":
            raise Exception("Don't execute change set")

        retry_on_throttling(
            self.cloudformation.execute_change_set,
            kwargs={
                'ChangeSetName': change_set_id,
            },
        )
        return True
