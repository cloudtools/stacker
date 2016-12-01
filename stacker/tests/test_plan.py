import unittest

import mock

from stacker.context import Context
from stacker.exceptions import CyclicDependencyError
from stacker.plan import (
    Step,
    Plan,
)
from stacker.status import (
    COMPLETE,
)
from stacker.stack import Stack

from .factories import generate_definition

count = 0


class TestStep(unittest.TestCase):

    def setUp(self):
        self.context = Context({"namespace": "namespace"})
        stack = Stack(
            definition=generate_definition("vpc", 1),
            context=self.context,
        )
        self.step = Step(stack=stack)

    def test_status(self):
        self.assertFalse(self.step.submitted)
        self.assertFalse(self.step.completed)
        self.step.submit()
        self.assertTrue(self.step.submitted)
        self.assertFalse(self.step.completed)
        self.step.complete()
        self.assertTrue(self.step.submitted)
        self.assertTrue(self.step.completed)


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.count = 0
        self.environment = {"namespace": "namespace"}
        self.context = Context(self.environment)

    def test_build_plan(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        plan = Plan(description="Test", sleep_func=None)
        plan.build([vpc, bastion])

        self.assertEqual(plan._dag.graph, {
            'namespace-bastion.1': set(['namespace-vpc.1']),
            'namespace-vpc.1': set([])})

    def test_build_plan_cyclic_dependencies(self):
        vpc = Stack(
            definition=generate_definition(
                'vpc', 1, requires=['namespace-bastion.1']),
            context=self.context)
        bastion = Stack(
            definition=generate_definition(
                'bastion', 1, requires=['namespace-vpc.1']),
            context=self.context)

        plan = Plan(description="Test", sleep_func=None)

        with self.assertRaises(CyclicDependencyError):
            plan.build([vpc, bastion])

    def test_execute_plan(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        plan = Plan(description="Test", sleep_func=None)
        plan.build([vpc, bastion])

        steps = []

        def fn(stack, status=None):
            steps.append(stack.fqn)
            return COMPLETE

        plan.execute(fn)

        self.assertEqual(steps, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_reverse(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        plan = Plan(description="Test", reverse=True, sleep_func=None)
        plan.build([vpc, bastion])

        steps = []

        def fn(stack, status=None):
            steps.append(stack.fqn)
            return COMPLETE

        plan.execute(fn)

        self.assertEqual(steps, ['namespace-bastion.1', 'namespace-vpc.1'])

    @mock.patch("stacker.plan.os")
    @mock.patch("stacker.plan.open", mock.mock_open(), create=True)
    def test_dump(self, *args):
        plan = Plan(description="Test", sleep_func=None)
        stacks = []
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides["requires"] = [previous_stack.fqn]
            stack = Stack(
                definition=generate_definition("vpc", i, **overrides),
                context=self.context,
            )
            previous_stack = stack
            stacks.append(stack)

        plan.build(stacks)
        plan.dump("test")
