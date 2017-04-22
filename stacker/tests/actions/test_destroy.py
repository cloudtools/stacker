import unittest

import mock

from stacker.actions import destroy
from stacker.context import Context
from stacker.exceptions import StackDoesNotExist
from stacker.status import (
    COMPLETE,
    PENDING,
    SKIPPED,
    SUBMITTED,
)


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
        self.assertEqual(
            {
                'namespace-vpc': set(
                    [
                        'namespace-db',
                        'namespace-instance',
                        'namespace-bastion']),
                'namespace-other': set([]),
                'namespace-bastion': set(
                    [
                        'namespace-instance',
                        'namespace-db']),
                'namespace-instance': set(
                    [
                        'namespace-db']),
                'namespace-db': set(
                    [
                        'namespace-other'])},
            plan.dag.graph,
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
        step = mock.MagicMock()
        step.name = "vpc"

        # Simulate the provider not being able to find the stack (a result of
        # it being successfully deleted)
        self.action.provider = mock.MagicMock()
        self.action.provider.get_stack.side_effect = StackDoesNotExist("mock")
        step.status = PENDING
        status = self.action._destroy_stack(step)
        # if we haven't processed the step (ie. has never been SUBMITTED,
        # should be skipped)
        self.assertEqual(status, SKIPPED)
        step.status = SUBMITTED
        status = self.action._destroy_stack(step)
        # if we have processed the step and then can't find the stack, it means
        # we successfully deleted it
        self.assertEqual(status, COMPLETE)
