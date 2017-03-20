import unittest
from datetime import datetime

from mock import patch
from botocore.stub import Stubber
import boto3

from ....providers.aws.interactive import (
    requires_replacement,
    ask_for_approval,
    wait_till_change_set_complete,
    create_change_set,
)

from .... import exceptions


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


class TestInteractiveProvider(unittest.TestCase):
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

    def test_ask_for_approval(self):
        get_input_path = "stacker.providers.aws.interactive.get_raw_input"
        with patch(get_input_path, return_value="y"):
            self.assertIsNone(ask_for_approval([]))

        for v in ("n", "N", "x", "\n"):
            with patch(get_input_path, return_value=v):
                with self.assertRaises(exceptions.CancelExecution):
                    ask_for_approval([])

        with patch(get_input_path, side_effect=["v", "n"]) as mock_get_input:
            with patch("yaml.safe_dump") as mock_safe_dump:
                with self.assertRaises(exceptions.CancelExecution):
                    ask_for_approval([], True)
                self.assertEqual(mock_safe_dump.call_count, 1)
            self.assertEqual(mock_get_input.call_count, 2)

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
