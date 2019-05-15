from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import range
import copy
from datetime import datetime
import random
import string
import threading
import unittest

from mock import patch, MagicMock
from botocore.stub import Stubber
from botocore.exceptions import ClientError, UnStubbedResponseError
import boto3

from stacker.actions.diff import DictValue

from stacker.providers.base import Template
from stacker.session_cache import get_session

from stacker.providers.aws import default

from stacker.providers.aws.default import (
    DEFAULT_CAPABILITIES,
    MAX_TAIL_RETRIES,
    Provider,
    requires_replacement,
    ask_for_approval,
    wait_till_change_set_complete,
    create_change_set,
    summarize_params_diff,
    generate_cloudformation_args,
)

from stacker import exceptions

from stacker.stack import Stack


def random_string(length=12):
    """ Returns a random string of variable length.

    Args:
        length (int): The # of characters to use in the random string.

    Returns:
        str: The random string.
    """

    return ''.join(
        [random.choice(string.ascii_letters) for _ in range(length)])


def generate_describe_stacks_stack(stack_name,
                                   creation_time=None,
                                   stack_status="CREATE_COMPLETE",
                                   tags=None):
    tags = tags or []
    return {
        "StackName": stack_name,
        "CreationTime": creation_time or datetime(2015, 1, 1),
        "StackStatus": stack_status,
        "Tags": tags
    }


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
            "CAPABILITY_AUTO_EXPAND"
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


class TestMethods(unittest.TestCase):
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

    @patch("stacker.providers.aws.default.format_params_diff")
    def test_ask_for_approval(self, patched_format):
        get_input_path = "stacker.ui.get_raw_input"
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

    @patch("stacker.providers.aws.default.format_params_diff")
    def test_ask_for_approval_with_params_diff(self, patched_format):
        get_input_path = "stacker.ui.get_raw_input"
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

        self.stubber.add_response(
            "delete_change_set",
            {},
            expected_params={"ChangeSetName": "CHANGESETID"}
        )

        with self.stubber:
            with self.assertRaises(exceptions.StackDidNotChange):
                create_change_set(
                    cfn_client=self.cfn, fqn="my-fake-stack",
                    template=Template(url="http://fake.template.url.com/"),
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
                    template=Template(url="http://fake.template.url.com/"),
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
                    template=Template(url="http://fake.template.url.com/"),
                    parameters=[], tags=[]
                )

    def test_generate_cloudformation_args(self):
        stack_name = "mystack"
        template_url = "http://fake.s3url.com/blah.json"
        template_body = '{"fake_body": "woot"}'
        std_args = {
            "stack_name": stack_name, "parameters": [], "tags": [],
            "template": Template(url=template_url)}
        std_return = {"StackName": stack_name, "Parameters": [], "Tags": [],
                      "Capabilities": DEFAULT_CAPABILITIES,
                      "TemplateURL": template_url}
        result = generate_cloudformation_args(**std_args)
        self.assertEqual(result, std_return)

        result = generate_cloudformation_args(service_role="FakeRole",
                                              **std_args)
        service_role_result = copy.deepcopy(std_return)
        service_role_result["RoleARN"] = "FakeRole"
        self.assertEqual(result, service_role_result)

        result = generate_cloudformation_args(change_set_name="MyChanges",
                                              **std_args)
        change_set_result = copy.deepcopy(std_return)
        change_set_result["ChangeSetName"] = "MyChanges"
        self.assertEqual(result, change_set_result)

        # Check stack policy
        stack_policy = Template(body="{}")
        result = generate_cloudformation_args(stack_policy=stack_policy,
                                              **std_args)
        stack_policy_result = copy.deepcopy(std_return)
        stack_policy_result["StackPolicyBody"] = "{}"
        self.assertEqual(result, stack_policy_result)

        # If not TemplateURL is provided, use TemplateBody
        std_args["template"] = Template(body=template_body)
        template_body_result = copy.deepcopy(std_return)
        del(template_body_result["TemplateURL"])
        template_body_result["TemplateBody"] = template_body
        result = generate_cloudformation_args(**std_args)
        self.assertEqual(result, template_body_result)


class TestProviderDefaultMode(unittest.TestCase):
    def setUp(self):
        region = "us-east-1"
        self.session = get_session(region=region)
        self.provider = Provider(
            self.session, region=region, recreate_failed=False)
        self.stubber = Stubber(self.provider.cloudformation)

    def test_get_stack_stack_does_not_exist(self):
        stack_name = "MockStack"
        self.stubber.add_client_error(
            "describe_stacks",
            service_error_code="ValidationError",
            service_message="Stack with id %s does not exist" % stack_name,
            expected_params={"StackName": stack_name}
        )

        with self.assertRaises(exceptions.StackDoesNotExist):
            with self.stubber:
                self.provider.get_stack(stack_name)

    def test_get_stack_stack_exists(self):
        stack_name = "MockStack"
        stack_response = {
            "Stacks": [generate_describe_stacks_stack(stack_name)]
        }
        self.stubber.add_response(
            "describe_stacks",
            stack_response,
            expected_params={"StackName": stack_name}
        )

        with self.stubber:
            response = self.provider.get_stack(stack_name)

        self.assertEqual(response["StackName"], stack_name)

    def test_select_update_method(self):
        for i in [[{'force_interactive': True,
                    'force_change_set': False},
                   self.provider.interactive_update_stack],
                  [{'force_interactive': False,
                    'force_change_set': False},
                   self.provider.default_update_stack],
                  [{'force_interactive': False,
                    'force_change_set': True},
                   self.provider.noninteractive_changeset_update],
                  [{'force_interactive': True,
                    'force_change_set': True},
                   self.provider.interactive_update_stack]]:
            self.assertEquals(
                self.provider.select_update_method(**i[0]),
                i[1]
            )

    def test_prepare_stack_for_update_completed(self):
        stack_name = "MockStack"
        stack = generate_describe_stacks_stack(
            stack_name, stack_status="UPDATE_COMPLETE")

        with self.stubber:
            self.assertTrue(
                self.provider.prepare_stack_for_update(stack, []))

    def test_prepare_stack_for_update_in_progress(self):
        stack_name = "MockStack"
        stack = generate_describe_stacks_stack(
            stack_name, stack_status="UPDATE_IN_PROGRESS")

        with self.assertRaises(exceptions.StackUpdateBadStatus) as raised:
            with self.stubber:
                self.provider.prepare_stack_for_update(stack, [])

            self.assertIn('in-progress', str(raised.exception))

    def test_prepare_stack_for_update_non_recreatable(self):
        stack_name = "MockStack"
        stack = generate_describe_stacks_stack(
            stack_name, stack_status="REVIEW_IN_PROGRESS")

        with self.assertRaises(exceptions.StackUpdateBadStatus) as raised:
            with self.stubber:
                self.provider.prepare_stack_for_update(stack, [])

        self.assertIn('Unsupported state', str(raised.exception))

    def test_prepare_stack_for_update_disallowed(self):
        stack_name = "MockStack"
        stack = generate_describe_stacks_stack(
            stack_name, stack_status="ROLLBACK_COMPLETE")

        with self.assertRaises(exceptions.StackUpdateBadStatus) as raised:
            with self.stubber:
                self.provider.prepare_stack_for_update(stack, [])

        self.assertIn('re-creation is disabled', str(raised.exception))
        # Ensure we point out to the user how to enable re-creation
        self.assertIn('--recreate-failed', str(raised.exception))

    def test_prepare_stack_for_update_bad_tags(self):
        stack_name = "MockStack"
        stack = generate_describe_stacks_stack(
            stack_name, stack_status="ROLLBACK_COMPLETE")

        self.provider.recreate_failed = True

        with self.assertRaises(exceptions.StackUpdateBadStatus) as raised:
            with self.stubber:
                self.provider.prepare_stack_for_update(
                    stack,
                    tags=[{'Key': 'stacker_namespace', 'Value': 'test'}])

        self.assertIn('tags differ', str(raised.exception).lower())

    def test_prepare_stack_for_update_recreate(self):
        stack_name = "MockStack"
        stack = generate_describe_stacks_stack(
            stack_name, stack_status="ROLLBACK_COMPLETE")

        self.stubber.add_response(
            "delete_stack",
            {},
            expected_params={"StackName": stack_name}
        )

        self.provider.recreate_failed = True

        with self.stubber:
            self.assertFalse(
                self.provider.prepare_stack_for_update(stack, []))

    def test_noninteractive_changeset_update_no_stack_policy(self):
        stack_name = "MockStack"

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
            self.provider.noninteractive_changeset_update(
                fqn=stack_name,
                template=Template(url="http://fake.template.url.com/"),
                old_parameters=[],
                parameters=[], stack_policy=None, tags=[],
            )

    def test_noninteractive_changeset_update_with_stack_policy(self):
        stack_name = "MockStack"

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

        self.stubber.add_response("set_stack_policy", {})

        self.stubber.add_response("execute_change_set", {})

        with self.stubber:
            self.provider.noninteractive_changeset_update(
                fqn=stack_name,
                template=Template(url="http://fake.template.url.com/"),
                old_parameters=[],
                parameters=[], stack_policy=Template(body="{}"), tags=[],
            )

    def test_tail_stack_retry_on_missing_stack(self):
        stack_name = "SlowToCreateStack"
        stack = MagicMock(spec=Stack)
        stack.fqn = "my-namespace-{}".format(stack_name)

        default.TAIL_RETRY_SLEEP = .01

        # Ensure the stack never appears before we run out of retries
        for i in range(MAX_TAIL_RETRIES + 5):
            self.stubber.add_client_error(
                "describe_stack_events",
                service_error_code="ValidationError",
                service_message="Stack [{}] does not exist".format(stack_name),
                http_status_code=400,
                response_meta={"attempt": i + 1},
            )

        with self.stubber:
            try:
                self.provider.tail_stack(stack, threading.Event())
            except ClientError as exc:
                self.assertEqual(
                    exc.response["ResponseMetadata"]["attempt"],
                    MAX_TAIL_RETRIES
                )

    def test_tail_stack_retry_on_missing_stack_eventual_success(self):
        stack_name = "SlowToCreateStack"
        stack = MagicMock(spec=Stack)
        stack.fqn = "my-namespace-{}".format(stack_name)

        default.TAIL_RETRY_SLEEP = .01
        default.GET_EVENTS_SLEEP = .01

        rcvd_events = []

        def mock_log_func(e):
            rcvd_events.append(e)

        def valid_event_response(stack, event_id):
            return {
                "StackEvents": [
                    {
                        "StackId": stack.fqn + "12345",
                        "EventId": event_id,
                        "StackName": stack.fqn,
                        "Timestamp": datetime.now()
                    },
                ]
            }

        # Ensure the stack never appears before we run out of retries
        for i in range(3):
            self.stubber.add_client_error(
                "describe_stack_events",
                service_error_code="ValidationError",
                service_message="Stack [{}] does not exist".format(stack_name),
                http_status_code=400,
                response_meta={"attempt": i + 1},
            )

        self.stubber.add_response(
            "describe_stack_events",
            valid_event_response(stack, "InitialEvents")
        )

        self.stubber.add_response(
            "describe_stack_events",
            valid_event_response(stack, "Event1")
        )

        with self.stubber:
            try:
                self.provider.tail_stack(stack, threading.Event(),
                                         log_func=mock_log_func)
            except UnStubbedResponseError:
                # Eventually we run out of responses - could not happen in
                # regular execution
                # normally this would just be dealt with when the threads were
                # shutdown, but doing so here is a little difficult because
                # we can't control the `tail_stack` loop
                pass

        self.assertEqual(rcvd_events[0]["EventId"], "Event1")


class TestProviderInteractiveMode(unittest.TestCase):
    def setUp(self):
        region = "us-east-1"
        self.session = get_session(region=region)
        self.provider = Provider(
            self.session, interactive=True, recreate_failed=True)
        self.stubber = Stubber(self.provider.cloudformation)

    def test_successful_init(self):
        replacements = True
        p = Provider(self.session, interactive=True,
                     replacements_only=replacements)
        self.assertEqual(p.replacements_only, replacements)

    @patch("stacker.providers.aws.default.ask_for_approval")
    def test_update_stack_execute_success_no_stack_policy(self,
                                                          patched_approval):
        stack_name = "my-fake-stack"

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
                fqn=stack_name,
                template=Template(url="http://fake.template.url.com/"),
                old_parameters=[],
                parameters=[], tags=[]
            )

        patched_approval.assert_called_with(full_changeset=changes,
                                            params_diff=[],
                                            include_verbose=True)

        self.assertEqual(patched_approval.call_count, 1)

    @patch("stacker.providers.aws.default.ask_for_approval")
    def test_update_stack_execute_success_with_stack_policy(self,
                                                            patched_approval):
        stack_name = "my-fake-stack"

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

        self.stubber.add_response("set_stack_policy", {})

        self.stubber.add_response("execute_change_set", {})

        with self.stubber:
            self.provider.update_stack(
                fqn=stack_name,
                template=Template(url="http://fake.template.url.com/"),
                old_parameters=[],
                parameters=[], tags=[],
                stack_policy=Template(body="{}"),
            )

        patched_approval.assert_called_with(full_changeset=changes,
                                            params_diff=[],
                                            include_verbose=True)

        self.assertEqual(patched_approval.call_count, 1)

    def test_select_update_method(self):
        for i in [[{'force_interactive': False,
                    'force_change_set': False},
                   self.provider.interactive_update_stack],
                  [{'force_interactive': True,
                    'force_change_set': False},
                   self.provider.interactive_update_stack],
                  [{'force_interactive': False,
                    'force_change_set': True},
                   self.provider.interactive_update_stack],
                  [{'force_interactive': True,
                    'force_change_set': True},
                   self.provider.interactive_update_stack]]:
            self.assertEquals(
                self.provider.select_update_method(**i[0]),
                i[1]
            )
