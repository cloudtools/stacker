import unittest
from datetime import datetime
import random
import string

from mock import patch
from botocore.stub import Stubber
import boto3

from ....actions.diff import DictValue

from ....providers.aws.interactive import (
    Provider,
    requires_replacement,
    ask_for_approval,
    wait_till_change_set_complete,
    create_change_set,
    summarize_params_diff
)

from .... import exceptions


def random_string(length=12):
    """ Returns a random string of variable length.

    Args:
        length (int): The # of characters to use in the random string.

    Returns:
        str: The random string.
    """

    return ''.join(
        [random.choice(string.ascii_letters) for _ in range(length)])


def generate_resource_change(replacement=True):
    resource_change = {
        "Action": "Modify",
        "Details": [],
        "LogicalResourceId": "Fake",
        "PhysicalResourceId": "arn:aws:fake",
        "Replacement": "True" if replacement else "False",
        "ResourceType": "AWS::Fake",
        "Scope": ["Properties"],
    }
    return {
        "ResourceChange": resource_change,
        "Type": "Resource",
    }


def generate_change_set_response(status, execution_status="AVAILABLE",
                                 changes=[], status_reason="FAKE"):
    return {
        "ChangeSetName": "string",
        "ChangeSetId": "string",
        "StackId": "string",
        "StackName": "string",
        "Description": "string",
        "Parameters": [
            {
                "ParameterKey": "string",
                "ParameterValue": "string",
                "UsePreviousValue": False
            },
        ],
        "CreationTime": datetime(2015, 1, 1),
        "ExecutionStatus": execution_status,
        "Status": status,
        "StatusReason": status_reason,
        "NotificationARNs": [
            "string",
        ],
        "Capabilities": [
            "CAPABILITY_NAMED_IAM",
        ],
        "Tags": [
            {
                "Key": "string",
                "Value": "string"
            },
        ],
        "Changes": changes,
        "NextToken": "string"
    }


def generate_change(action="Modify", resource_type="EC2::Instance",
                    replacement="False", requires_recreation="Never"):
    """ Generate a minimal change for a changeset """
    return {
        "Type": "Resource",
        "ResourceChange": {
            "Action": action,
            "LogicalResourceId": random_string(),
            "PhysicalResourceId": random_string(),
            "ResourceType": resource_type,
            "Replacement": replacement,
            "Scope": ["Properties"],
            "Details": [
                {
                    "Target": {
                        "Attribute": "Properties",
                        "Name": random_string(),
                        "RequiresRecreation": requires_recreation
                    },
                    "Evaluation": "Static",
                    "ChangeSource": "ResourceReference",
                    "CausingEntity": random_string()
                },
            ]
        }
    }


class TestInteractiveProviderMethods(unittest.TestCase):
    def setUp(self):
        self.cfn = boto3.client("cloudformation")
        self.stubber = Stubber(self.cfn)

    def test_requires_replacement(self):
        changeset = [
            generate_resource_change(),
            generate_resource_change(replacement=False),
            generate_resource_change(),
        ]
        replacement = requires_replacement(changeset)
        self.assertEqual(len(replacement), 2)
        for resource in replacement:
            self.assertEqual(resource["ResourceChange"]["Replacement"], "True")

    def test_summarize_params_diff(self):
        unmodified_param = DictValue("ParamA", "new-param-value",
                                     "new-param-value")
        modified_param = DictValue("ParamB", "param-b-old-value",
                                   "param-b-new-value-delta")
        added_param = DictValue("ParamC", None, "param-c-new-value")
        removed_param = DictValue("ParamD", "param-d-old-value", None)

        params_diff = [
            unmodified_param,
            modified_param,
            added_param,
            removed_param,
        ]
        self.assertEqual(summarize_params_diff([]), "")
        self.assertEqual(summarize_params_diff(params_diff), '\n'.join([
            "Parameters Added: ParamC",
            "Parameters Removed: ParamD",
            "Parameters Modified: ParamB\n",
        ]))

        only_modified_params_diff = [modified_param]
        self.assertEqual(summarize_params_diff(only_modified_params_diff),
                         "Parameters Modified: ParamB\n")

        only_added_params_diff = [added_param]
        self.assertEqual(summarize_params_diff(only_added_params_diff),
                         "Parameters Added: ParamC\n")

        only_removed_params_diff = [removed_param]
        self.assertEqual(summarize_params_diff(only_removed_params_diff),
                         "Parameters Removed: ParamD\n")

    @patch("stacker.providers.aws.interactive.format_params_diff")
    def test_ask_for_approval(self, patched_format):
        get_input_path = "stacker.providers.aws.interactive.get_raw_input"
        with patch(get_input_path, return_value="y"):
            self.assertIsNone(ask_for_approval([], [], None))

        for v in ("n", "N", "x", "\n"):
            with patch(get_input_path, return_value=v):
                with self.assertRaises(exceptions.CancelExecution):
                    ask_for_approval([], [])

        with patch(get_input_path, side_effect=["v", "n"]) as mock_get_input:
            with patch("yaml.safe_dump") as mock_safe_dump:
                with self.assertRaises(exceptions.CancelExecution):
                    ask_for_approval([], [], True)
                self.assertEqual(mock_safe_dump.call_count, 1)
            self.assertEqual(mock_get_input.call_count, 2)

        self.assertEqual(patched_format.call_count, 0)

    @patch("stacker.providers.aws.interactive.format_params_diff")
    def test_ask_for_approval_with_params_diff(self, patched_format):
        get_input_path = "stacker.providers.aws.interactive.get_raw_input"
        params_diff = [
            DictValue('ParamA', None, 'new-param-value'),
            DictValue('ParamB', 'param-b-old-value', 'param-b-new-value-delta')
        ]
        with patch(get_input_path, return_value="y"):
            self.assertIsNone(ask_for_approval([], params_diff, None))

        for v in ("n", "N", "x", "\n"):
            with patch(get_input_path, return_value=v):
                with self.assertRaises(exceptions.CancelExecution):
                    ask_for_approval([], params_diff)

        with patch(get_input_path, side_effect=["v", "n"]) as mock_get_input:
            with patch("yaml.safe_dump") as mock_safe_dump:
                with self.assertRaises(exceptions.CancelExecution):
                    ask_for_approval([], params_diff, True)
                self.assertEqual(mock_safe_dump.call_count, 1)
            self.assertEqual(mock_get_input.call_count, 2)

        self.assertEqual(patched_format.call_count, 1)

    def test_wait_till_change_set_complete_success(self):
        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response("CREATE_COMPLETE")
        )
        with self.stubber:
            wait_till_change_set_complete(self.cfn, "FAKEID")

        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response("FAILED")
        )
        with self.stubber:
            wait_till_change_set_complete(self.cfn, "FAKEID")

    def test_wait_till_change_set_complete_failed(self):
        # Need 2 responses for try_count
        for i in range(2):
            self.stubber.add_response(
                "describe_change_set",
                generate_change_set_response("CREATE_PENDING")
            )
        with self.stubber:
            with self.assertRaises(exceptions.ChangesetDidNotStabilize):
                wait_till_change_set_complete(self.cfn, "FAKEID", try_count=2,
                                              sleep_time=.1)

    def test_create_change_set_stack_did_not_change(self):
        self.stubber.add_response(
            "create_change_set",
            {'Id': 'CHANGESETID', 'StackId': 'STACKID'}
        )

        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response(
                "FAILED", status_reason="Stack didn't contain changes."
            )
        )

        with self.stubber:
            with self.assertRaises(exceptions.StackDidNotChange):
                create_change_set(
                    cfn_client=self.cfn, fqn="my-fake-stack",
                    template_url="http://fake.template.url.com/",
                    parameters=[], tags=[]
                )

    def test_create_change_set_unhandled_failed_status(self):
        self.stubber.add_response(
            "create_change_set",
            {'Id': 'CHANGESETID', 'StackId': 'STACKID'}
        )

        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response(
                "FAILED", status_reason="Some random bad thing."
            )
        )

        with self.stubber:
            with self.assertRaises(exceptions.UnhandledChangeSetStatus):
                create_change_set(
                    cfn_client=self.cfn, fqn="my-fake-stack",
                    template_url="http://fake.template.url.com/",
                    parameters=[], tags=[]
                )

    def test_create_change_set_bad_execution_status(self):
        self.stubber.add_response(
            "create_change_set",
            {'Id': 'CHANGESETID', 'StackId': 'STACKID'}
        )

        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response(
                status="CREATE_COMPLETE", execution_status="UNAVAILABLE",
            )
        )

        with self.stubber:
            with self.assertRaises(exceptions.UnableToExecuteChangeSet):
                create_change_set(
                    cfn_client=self.cfn, fqn="my-fake-stack",
                    template_url="http://fake.template.url.com/",
                    parameters=[], tags=[]
                )


class TestInteractiveProvider(unittest.TestCase):
    def setUp(self):
        region = "us-east-1"
        self.provider = Provider(region=region)
        self.stubber = Stubber(self.provider.cloudformation)

    def test_successful_init(self):
        region = "us-east-1"
        replacements = True
        p = Provider(region=region, replacements_only=replacements)
        self.assertEqual(p.region, region)
        self.assertEqual(p.replacements_only, replacements)

    @patch("stacker.providers.aws.interactive.ask_for_approval")
    def test_update_stack_execute_success(self, patched_approval):
        self.stubber.add_response(
            "create_change_set",
            {'Id': 'CHANGESETID', 'StackId': 'STACKID'}
        )
        changes = []
        changes.append(generate_change())

        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response(
                status="CREATE_COMPLETE", execution_status="AVAILABLE",
                changes=changes,
            )
        )

        self.stubber.add_response("execute_change_set", {})

        with self.stubber:
            self.provider.update_stack(
                fqn="my-fake-stack",
                template_url="http://fake.template.url.com/",
                old_parameters=[],
                parameters=[], tags=[]
            )

        patched_approval.assert_called_with(full_changeset=changes,
                                            params_diff=[],
                                            include_verbose=True)

        self.assertEqual(patched_approval.call_count, 1)

    @patch("stacker.providers.aws.interactive.ask_for_approval")
    def test_update_stack_diff_success(self, patched_approval):
        self.stubber.add_response(
            "create_change_set",
            {'Id': 'CHANGESETID', 'StackId': 'STACKID'}
        )
        changes = []
        changes.append(generate_change())

        self.stubber.add_response(
            "describe_change_set",
            generate_change_set_response(
                status="CREATE_COMPLETE", execution_status="AVAILABLE",
                changes=changes,
            )
        )

        self.stubber.add_response("delete_change_set", {})

        with self.stubber:
            self.provider.update_stack(
                fqn="my-fake-stack",
                template_url="http://fake.template.url.com/",
                old_parameters=[],
                parameters=[], tags=[], diff=True
            )

        self.assertEqual(patched_approval.call_count, 0)
