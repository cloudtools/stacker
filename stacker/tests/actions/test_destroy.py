from contextlib import nested
import unittest

import mock

from stacker.actions import destroy
from stacker.context import Context
from stacker.plan import SUBMITTED, PENDING, COMPLETE, SKIPPED
from stacker.providers import aws


class MockStack(object):
    """Mock our local Stacker stack and an AWS provider stack"""

    def __init__(self, name, tags=None, **kwargs):
        self.name = name
        self.fqn = name
        self.provider_stack = mock.MagicMock(stack_name=name, tags=tags or {})


class TestDestroyAction(unittest.TestCase):

    def setUp(self):
        context = Context('namespace')
        self.action = destroy.Action(context, provider=aws.Provider('us-east-1'))
        self.stack_definitions = [
            {'name': 'vpc'},
            {'name': 'bastion'},
            {'name': 'instance'},
            {'name': 'db'},
            {'name': 'other'},
        ]

    def test_generate_plan(self):
        stacks = [
            MockStack('vpc'),
            MockStack('bastion', tags={'required_stacks': 'vpc'}),
            MockStack('instance', tags={'required_stacks': 'vpc:bastion'}),
            MockStack('db', tags={'required_stacks': 'instance:vpc:bastion'}),
            MockStack('other', tags={'required_stacks': 'db'}),
        ]
        stacks_dict = dict((stack.name, stack.provider_stack) for stack in stacks)

        def get_stack(stack_name):
            return stacks_dict.get(stack_name)

        mocks = [
            mock.patch.object(self.action.provider, 'get_stack'),
            mock.patch.object(self.action.context, 'get_stacks'),
        ]
        with nested(*mocks) as (mock_get_stack, mock_get_stacks):
            mock_get_stacks.return_value = stacks
            mock_get_stack.side_effect = get_stack
            plan = self.action._generate_plan()
        self.assertEqual(['other', 'db', 'instance', 'bastion', 'vpc'], plan.keys())

    def test_only_execute_plan_when_forced(self):
        with mock.patch.object(self.action, '_generate_plan') as mock_generate_plan:
            self.action.run(force=False)
            self.assertEqual(mock_generate_plan().execute.call_count, 0)

    def test_execute_plan_when_forced(self):
        with mock.patch.object(self.action, '_generate_plan') as mock_generate_plan:
            self.action.run(force=True)
            self.assertEqual(mock_generate_plan().execute.call_count, 1)

    def test_destroy_stack_complete_if_state_pending(self):
        # Simulate the provider not being able to find the stack (a result of
        # it being successfully deleted)
        self.action.provider = mock.MagicMock()
        self.action.provider.get_stack.return_value = None
        status = self.action._destroy_stack({}, MockStack('vpc'), status=SUBMITTED)
        # if we haven't processed the step (ie. has never been PENDING, should be skipped)
        self.assertEqual(status, SKIPPED)
        status = self.action._destroy_stack({}, MockStack('vpc'), status=PENDING)
        # if we have processed the step and then can't find the stack, it means
        # we successfully deleted it
        self.assertEqual(status, COMPLETE)
