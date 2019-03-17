from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import unittest

import mock

from stacker.actions import destroy
from stacker.context import Context, Config
from stacker.exceptions import StackDoesNotExist
from stacker.status import (
    COMPLETE,
    PENDING,
    SKIPPED,
    SUBMITTED,
)

from ..factories import MockThreadingEvent, MockProviderBuilder


class MockStack(object):
    """Mock our local Stacker stack and an AWS provider stack"""

    def __init__(self, name, tags=None, **kwargs):
        self.name = name
        self.fqn = name
        self.region = None
        self.profile = None
        self.requires = []


class TestDestroyAction(unittest.TestCase):

    def setUp(self):
        config = Config({
            "namespace": "namespace",
            "stacks": [
                {"name": "vpc"},
                {"name": "bastion", "requires": ["vpc"]},
                {"name": "db", "requires": ["vpc", "bastion"]},
                {"name": "instance", "requires": ["db", "vpc", "bastion"]},
                {"name": "other", "requires": []},
            ],
            "destroy_hooks": [
                {"name": "before-db-hook-1",
                 "path": "stacker.hooks.no_op",
                 "args": {"x": "${output db::whatever}"}},
                {"name": "before-db-hook-2",
                 "path": "stacker.hooks.no_op",
                 "requires": ["db"]},
                {"name": "after-db-hook",
                 "path": "stacker.hooks.no_op",
                 "required_by": ["db"]}
            ],
            "pre_destroy": [
                {"name": "pre-destroy-hook",
                 "path": "stacker.hooks.no_op"}
            ],
            "post_destroy": [
                {"name": "post-destroy-hook",
                 "path": "stacker.hooks.no_op"}
            ]
        })
        self.context = Context(config=config)
        self.action = destroy.Action(self.context,
                                     cancel=MockThreadingEvent())

    def test_generate_plan(self):
        plan = self.action._generate_plan()
        plan.graph.transitive_reduction()

        self.assertEqual(
            {
                'pre-destroy-hook': set(),
                'pre_destroy_hooks': {'pre-destroy-hook'},
                'pre_destroy': {'pre_destroy_hooks'},
                'destroy': {'vpc', 'other'},
                'post_destroy': {'destroy', 'after-db-hook'},
                'post_destroy_hooks': {'post_destroy'},
                'post-destroy-hook': {'post_destroy_hooks'},

                'before-db-hook-1': {'pre_destroy'},
                'before-db-hook-2': {'pre_destroy'},
                'after-db-hook': {'db'},

                'instance': {'pre_destroy'},
                'db': {'instance', 'before-db-hook-1', 'before-db-hook-2'},
                'bastion': {'db'},
                'vpc': {'bastion'},
                'other': {'pre_destroy'},
            },
            dict(plan.graph.to_dict())
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
        provider = mock.MagicMock()
        provider.get_stack.side_effect = StackDoesNotExist("mock")
        self.action.provider_builder = MockProviderBuilder(provider)
        status = self.action._destroy_stack(MockStack("vpc"), status=PENDING)
        # if we haven't processed the step (ie. has never been SUBMITTED,
        # should be skipped)
        self.assertEqual(status, SKIPPED)
        status = self.action._destroy_stack(MockStack("vpc"), status=SUBMITTED)
        # if we have processed the step and then can't find the stack, it means
        # we successfully deleted it
        self.assertEqual(status, COMPLETE)

    def test_destroy_stack_step_statuses(self):
        mock_provider = mock.MagicMock()
        stacks_dict = self.context.get_stacks_dict()

        def get_stack(stack_name):
            return stacks_dict.get(stack_name)

        plan = self.action._generate_plan()
        step = plan.get("vpc")
        # we need the AWS provider to generate the plan, but swap it for
        # the mock one to make the test easier
        self.action.provider_builder = MockProviderBuilder(mock_provider)

        # simulate stack doesn't exist and we haven't submitted anything for
        # deletion
        mock_provider.get_stack.side_effect = StackDoesNotExist("mock")

        step.run()
        self.assertEqual(step.status, SKIPPED)

        # simulate stack getting successfully deleted
        mock_provider.get_stack.side_effect = get_stack
        mock_provider.is_stack_destroyed.return_value = False
        mock_provider.is_stack_in_progress.return_value = False

        step._run_once()
        self.assertEqual(step.status, SUBMITTED)
        mock_provider.is_stack_destroyed.return_value = False
        mock_provider.is_stack_in_progress.return_value = True

        step._run_once()
        self.assertEqual(step.status, SUBMITTED)
        mock_provider.is_stack_destroyed.return_value = True
        mock_provider.is_stack_in_progress.return_value = False

        step._run_once()
        self.assertEqual(step.status, COMPLETE)
