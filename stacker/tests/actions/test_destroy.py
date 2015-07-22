from contextlib import nested
import unittest

import mock

from stacker.actions import destroy
from stacker.context import Context
from stacker.plan import (
    COMPLETE,
    PENDING,
    SKIPPED,
    SUBMITTED,
)
from stacker.providers import aws


class MockStack(object):
    """Mock our local Stacker stack and an AWS provider stack"""

    def __init__(self, name, tags=None, **kwargs):
        self.name = name
        self.fqn = name
        self.provider_stack = mock.MagicMock(stack_name=name, tags=tags or {})
        self.requires = []


class TestDestroyAction(unittest.TestCase):

    def setUp(self):
        self.context = Context('namespace')
        self.action = destroy.Action(self.context, provider=aws.Provider('us-east-1'))
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

    def test_destroy_stack_complete_if_state_submitted(self):
        # Simulate the provider not being able to find the stack (a result of
        # it being successfully deleted)
        self.action.provider = mock.MagicMock()
        self.action.provider.get_stack.return_value = None
        status = self.action._destroy_stack({}, MockStack('vpc'), status=PENDING)
        # if we haven't processed the step (ie. has never been SUBMITTED, should be skipped)
        self.assertEqual(status, SKIPPED)
        status = self.action._destroy_stack({}, MockStack('vpc'), status=SUBMITTED)
        # if we have processed the step and then can't find the stack, it means
        # we successfully deleted it
        self.assertEqual(status, COMPLETE)

    def test_destroy_stack_in_parallel(self):
        mock_provider = mock.MagicMock()

        stacks = [
            MockStack('vpc'),
            MockStack('bastion', tags={'required_stacks': 'vpc'}),
            MockStack('instance', tags={'required_stacks': 'vpc'}),
            MockStack('db', tags={'required_stacks': 'vpc'}),
        ]
        stacks_dict = dict((stack.name, stack.provider_stack) for stack in stacks)

        results = {'_count': 0}

        def get_stack(stack_name):
            return stacks_dict.get(stack_name)

        def get_stack_staggered(stack_name):
            results['_count'] += 1
            if not results['_count'] % 2:
                return None
            return stacks_dict.get(stack_name)

        def wait_func(*args):
            # we want "get_stack" above to return staggered results for the stack
            # being "deleted" to simulate waiting on stacks to complete
            mock_provider.get_stack.side_effect = get_stack_staggered

            non_test_keys = [key for key in results if not key.startswith('_')]
            if len(non_test_keys) >= 3 and '_dependencies_deleted' not in results:
                # vpc should not have been deleted until all other stacks have been deleted
                self.assertNotIn('vpc', results)
                results['_dependencies_deleted'] = True

        mocks = [
            mock.patch.object(self.action.provider, 'get_stack'),
            mock.patch.object(self.action.context, 'get_stacks'),
        ]
        with nested(*mocks) as (mock_get_stack, mock_get_stacks):
            mock_get_stack.side_effect = get_stack
            mock_get_stacks.return_value = stacks
            # We need the AWS provider to generate the plan, we'll swap it for
            # a mock provider to make the test easier below
            plan = self.action._generate_plan()

        plan._wait_func = wait_func

        # swap for mock provider
        plan.provider = mock_provider
        self.action.provider = mock_provider

        # we want "get_stack" to return the mock stacks above on the first
        # pass. "wait_func" will simulate the stack being deleted every second
        # pass
        mock_provider.get_stack.side_effect = get_stack
        mock_provider.is_stack_destroyed.return_value = False
        mock_provider.is_stack_in_progress.return_value = True
        plan.execute(results)

    def test_destroy_stack_step_statuses(self):
        mock_provider = mock.MagicMock()

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
            plan = self.action._generate_plan()
            _, step = plan.list_pending()[0]
            # we need the AWS provider to generate the plan, but swap it for
            # the mock one to make the test easier
            self.action.provider = mock_provider

            # simulate stack doesn't exist and we haven't submitted anything for deletion
            mock_provider.get_stack.return_value = None
            status = step.run({})
            self.assertEqual(status, SKIPPED)

            # simulate stack getting successfully deleted
            mock_provider.get_stack.side_effect = get_stack
            mock_provider.is_stack_destroyed.return_value = False
            mock_provider.is_stack_in_progress.return_value = False
            status = step.run({})
            self.assertEqual(status, SUBMITTED)
            mock_provider.is_stack_destroyed.return_value = False
            mock_provider.is_stack_in_progress.return_value = True
            status = step.run({})
            self.assertEqual(status, SUBMITTED)
            mock_provider.is_stack_destroyed.return_value = True
            mock_provider.is_stack_in_progress.return_value = False
            status = step.run({})
            self.assertEqual(status, COMPLETE)
