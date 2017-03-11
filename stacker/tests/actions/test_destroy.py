import unittest

import mock

from stacker.actions import destroy
from stacker.context import Context
from stacker.exceptions import (
    StackDoesNotExist,
    DestoryWithoutNotificationQueue
)
from stacker.status import (
    SKIPPED,
    SUBMITTED,
)


class MockStack(object):

    """Mock our local Stacker stack and an AWS provider stack"""

    def __init__(self, name, tags=None, **kwargs):
        self.name = name
        self.fqn = name
        self.requires = []


class TestDestroyAction(unittest.TestCase):

    def setUp(self):
        self.context = Context({"namespace": "namespace"})
        self.context.config = {
            "stacks": [
                {"name": "vpc"},
                {"name": "bastion", "requires": ["vpc"]},
                {"name": "instance", "requires": ["vpc", "bastion"]},
                {"name": "db", "requires": ["instance", "vpc", "bastion"]},
                {"name": "other", "requires": ["db"]},
            ],
        }
        self.action = destroy.Action(self.context, provider=mock.MagicMock())

    def test_generate_plan(self):
        plan = self.action._generate_plan()
        stacks = ["other", "db", "instance", "bastion", "vpc"]
        self.assertEqual(
            [self.context.get_fqn(s) for s in stacks],
            plan.keys(),
        )

    def test_only_execute_plan_when_forced(self):
        with mock.patch.object(self.action, "_generate_plan") as \
                mock_generate_plan:
            self.action.run(force=False)
            self.assertEqual(mock_generate_plan().execute.call_count, 0)

    def test_execute_plan_when_forced(self):
        with mock.patch.object(self.action, "_generate_plan") as \
                mock_generate_plan:
            self.action.run(force=True)
            self.assertEqual(mock_generate_plan().execute.call_count, 1)

    def test_destroy_stack_complete_if_state_submitted(self):

        # Simulate the provider not being able to find the stack (a result of
        # it being successfully deleted)
        self.action.provider = mock.MagicMock()
        self.action.provider.get_stack.side_effect = StackDoesNotExist('mock')

        status = self.action._destroy_stack(MockStack('vpc'))
        # # if we haven't processed the step (ie. has never been SUBMITTED,
        # # should be skipped)
        self.assertEqual(status, SKIPPED)

        fake_stack = {"fqn": "vpc", "name": "vpc"}

        self.action.provider.get_stack.side_effect = None
        self.action.provider.get_stack.return_value = fake_stack
        self.action.provider.set_listener_topic_arn.return_value = None

        # Succesfully fails without notification arn
        with self.assertRaises(DestoryWithoutNotificationQueue):
            self.action._destroy_stack(MockStack("vpc"))

        fake_stack = {
            "fqn": "vpc",
            "name": "vpc",
            "NotificationARNs": ["test_arn"]
        }

        # Succesfully deletes the stack
        self.action.provider.get_stack.side_effect = None
        self.action.provider.get_stack.return_value = fake_stack
        status = self.action._destroy_stack(MockStack("vpc"))
        self.assertEqual(status, SUBMITTED)
