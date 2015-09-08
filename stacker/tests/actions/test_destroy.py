import unittest

import mock

from stacker.actions import destroy
from stacker.context import Context
from stacker.exceptions import StackDoesNotExist
from stacker.plan import (
    COMPLETE,
    PENDING,
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
        self.context = Context({'namespace': 'namespace'})
        self.context.config = {
            'stacks': [
                {'name': 'vpc'},
                {'name': 'bastion', 'requires': ['vpc']},
                {'name': 'instance', 'requires': ['vpc', 'bastion']},
                {'name': 'db', 'requires': ['instance', 'vpc', 'bastion']},
                {'name': 'other', 'requires': ['db']},
            ],
        }
        self.action = destroy.Action(self.context, provider=mock.MagicMock())

    def test_generate_plan(self):
        plan = self.action._generate_plan()
        self.assertEqual(
            [self.context.get_fqn(s) for s in ['other', 'db', 'instance', 'bastion', 'vpc']],
            plan.keys(),
        )

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
        self.action.provider.get_stack.side_effect = StackDoesNotExist('mock')
        status = self.action._destroy_stack(MockStack('vpc'), status=PENDING)
        # if we haven't processed the step (ie. has never been SUBMITTED, should be skipped)
        self.assertEqual(status, SKIPPED)
        status = self.action._destroy_stack(MockStack('vpc'), status=SUBMITTED)
        # if we have processed the step and then can't find the stack, it means
        # we successfully deleted it
        self.assertEqual(status, COMPLETE)

    def test_destroy_stack_in_parallel(self):
        count = {'_count': 0}
        mock_provider = mock.MagicMock()
        self.context.config = {
            'stacks': [
                {'name': 'vpc'},
                {'name': 'bastion', 'requires': ['vpc']},
                {'name': 'instance', 'requires': ['vpc']},
                {'name': 'db', 'requies': ['vpc']},
            ],
        }
        stacks_dict = self.context.get_stacks_dict()

        def get_stack(stack_name):
            return stacks_dict.get(stack_name)

        def get_stack_staggered(stack_name):
            count['_count'] += 1
            if not count['_count'] % 2:
                raise StackDoesNotExist(stack_name)
            return stacks_dict.get(stack_name)

        def wait_func(*args):
            # we want "get_stack" above to return staggered results for the stack
            # being "deleted" to simulate waiting on stacks to complete
            mock_provider.get_stack.side_effect = get_stack_staggered

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

        independent_stacks = filter(lambda x: x.name != 'vpc', self.context.get_stacks())
        while not plan._single_run():
            # vpc should be the last stack that is deleted
            if plan['namespace-vpc'].completed:
                self.assertFalse(plan.list_pending())

            # all of the independent stacks should be submitted at the same time
            if any([plan[stack.fqn].submitted for stack in independent_stacks]):
                self.assertTrue(all([plan[stack.fqn].submitted for stack in independent_stacks]))
            wait_func()

    def test_destroy_stack_step_statuses(self):
        mock_provider = mock.MagicMock()
        stacks_dict = self.context.get_stacks_dict()

        def get_stack(stack_name):
            return stacks_dict.get(stack_name)

        plan = self.action._generate_plan()
        _, step = plan.list_pending()[0]
        # we need the AWS provider to generate the plan, but swap it for
        # the mock one to make the test easier
        self.action.provider = mock_provider

        # simulate stack doesn't exist and we haven't submitted anything for deletion
        mock_provider.get_stack.side_effect = StackDoesNotExist('mock')
        status = step.run()
        self.assertEqual(status, SKIPPED)

        # simulate stack getting successfully deleted
        mock_provider.get_stack.side_effect = get_stack
        mock_provider.is_stack_destroyed.return_value = False
        mock_provider.is_stack_in_progress.return_value = False
        status = step.run()
        self.assertEqual(status, SUBMITTED)
        mock_provider.is_stack_destroyed.return_value = False
        mock_provider.is_stack_in_progress.return_value = True
        status = step.run()
        self.assertEqual(status, SUBMITTED)
        mock_provider.is_stack_destroyed.return_value = True
        mock_provider.is_stack_in_progress.return_value = False
        status = step.run()
        self.assertEqual(status, COMPLETE)
