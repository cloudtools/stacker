import unittest

import mock

from stacker.context import Context
from stacker.exceptions import GraphError
from stacker.lookups.registry import (
    register_lookup_handler,
    unregister_lookup_handler,
)
from stacker.plan import (
    Step,
    Plan,
)
from stacker.status import (
    COMPLETE,
    SKIPPED,
    CANCELLED,
)
from stacker.stack import Stack

from .factories import generate_definition

count = 0


class TestStep(unittest.TestCase):

    def setUp(self):
        stack = mock.MagicMock()
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
        register_lookup_handler("noop", lambda **kwargs: "test")

    def tearDown(self):
        unregister_lookup_handler("noop")

    def test_pan(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        plan = Plan(description="Test", steps=[Step(vpc), Step(bastion)])

        self.assertEqual(plan.dag.graph, {
            'namespace-bastion.1': set(['namespace-vpc.1']),
            'namespace-vpc.1': set([])})

    def test_execute_plan(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        calls = []

        def fn(step):
            calls.append(step.name)
            return COMPLETE

        plan = Plan(
            description="Test", steps=[Step(vpc, fn), Step(bastion, fn)])
        plan.execute()

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_cancelled(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        calls = []

        def fn(step):
            calls.append(step.name)
            if step == vpc_step:
                return CANCELLED
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)
        plan = Plan(description="Test", steps=[vpc_step, bastion_step])

        plan.execute()

        self.assertEquals(calls, ['namespace-vpc.1'])

    def test_execute_plan_skipped(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        calls = []

        def fn(step):
            calls.append(step.name)
            if step == vpc_step:
                return SKIPPED
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)

        plan = Plan(description="Test", steps=[vpc_step, bastion_step])
        plan.execute()

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_build_plan_missing_dependency(self):
        bastion = Stack(
            definition=generate_definition(
                'bastion', 1, requires=['namespace-vpc.1']),
            context=self.context)

        with self.assertRaises(GraphError) as expected:
            Plan(description="Test", steps=[Step(bastion, None)])
        message = ("Error detected when adding 'namespace-vpc.1' "
                   "as a dependency of 'namespace-bastion.1': node "
                   "namespace-vpc.1 does not exist")
        self.assertEqual(expected.exception.message, message)

    def test_build_plan_cyclic_dependencies(self):
        vpc = Stack(
            definition=generate_definition(
                'vpc', 1),
            context=self.context)
        db = Stack(
            definition=generate_definition(
                'db', 1, requires=['namespace-app.1']),
            context=self.context)
        app = Stack(
            definition=generate_definition(
                'app', 1, requires=['namespace-db.1']),
            context=self.context)

        with self.assertRaises(GraphError) as expected:
            Plan(
                description="Test",
                steps=[Step(vpc, None), Step(db, None), Step(app, None)])
        message = ("Error detected when adding 'namespace-db.1' "
                   "as a dependency of 'namespace-app.1': graph is "
                   "not acyclic")
        self.assertEqual(expected.exception.message, message)
