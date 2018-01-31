import os
import shutil
import tempfile

import unittest
import mock

from stacker.context import Context, Config
from stacker.util import stack_template_key_name
from stacker.lookups.registry import (
    register_lookup_handler,
    unregister_lookup_handler,
)
from stacker.plan2 import (
    Step,
    build_plan,
)
from stacker.exceptions import (
    CancelExecution,
    GraphError,
)
from stacker.status import (
    COMPLETE,
    SKIPPED,
    FAILED,
)
from stacker.stack import Stack

from .factories import generate_definition

count = 0


class TestStep(unittest.TestCase):

    def setUp(self):
        stack = mock.MagicMock()
        self.step = Step(stack=stack, fn=None)

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
        self.config = Config({"namespace": "namespace"})
        self.context = Context(config=self.config)
        register_lookup_handler("noop", lambda **kwargs: "test")

    def tearDown(self):
        unregister_lookup_handler("noop")

    def test_plan(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        plan = build_plan(description="Test", steps=[
            Step(vpc, fn=None), Step(bastion, fn=None)])

        self.assertEqual(plan.graph.to_dict(), {
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

        def fn(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        plan = build_plan(
            description="Test", steps=[Step(vpc, fn), Step(bastion, fn)])
        plan.execute()

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_filtered(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        db = Stack(
            definition=generate_definition('db', 1, requires=[vpc.fqn]),
            context=self.context)
        app = Stack(
            definition=generate_definition('app', 1, requires=[db.fqn]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        plan = build_plan(
            description="Test",
            steps=[Step(vpc, fn), Step(db, fn), Step(app, fn)],
            targets=['db.1'])
        self.assertTrue(plan.execute())

        self.assertEquals(calls, [
            'namespace-vpc.1', 'namespace-db.1'])

    def test_execute_plan_exception(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.fqn == vpc_step.name:
                raise ValueError('Boom')
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)
        plan = build_plan(description="Test", steps=[vpc_step, bastion_step])

        with self.assertRaises(ValueError):
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

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.fqn == vpc_step.name:
                return SKIPPED
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)

        plan = build_plan(description="Test", steps=[vpc_step, bastion_step])
        self.assertTrue(plan.execute())

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_failed(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)
        db = Stack(
            definition=generate_definition('db', 1),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.fqn == vpc_step.name:
                return FAILED
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)
        db_step = Step(db, fn)

        plan = build_plan(description="Test", steps=[
            vpc_step, bastion_step, db_step])
        self.assertFalse(plan.execute())

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-db.1'])

    def test_execute_plan_cancelled(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.fqn]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.fqn == vpc_step.name:
                raise CancelExecution
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)

        plan = build_plan(description="Test", steps=[
            vpc_step, bastion_step])
        self.assertTrue(plan.execute())

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_build_plan_missing_dependency(self):
        bastion = Stack(
            definition=generate_definition(
                'bastion', 1, requires=['namespace-vpc.1']),
            context=self.context)

        with self.assertRaises(GraphError) as expected:
            build_plan(description="Test", steps=[Step(bastion, None)])
        message = ("Error detected when adding 'namespace-vpc.1' "
                   "as a dependency of 'namespace-bastion.1': dependent node "
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
            build_plan(
                description="Test",
                steps=[Step(vpc, None), Step(db, None), Step(app, None)])
        message = ("Error detected when adding 'namespace-db.1' "
                   "as a dependency of 'namespace-app.1': graph is "
                   "not acyclic")
        self.assertEqual(expected.exception.message, message)

    @mock.patch("stacker.plan.os")
    @mock.patch("stacker.plan.open", mock.mock_open(), create=True)
    def test_dump(self, *args):
        requires = None
        steps = []

        for i in range(5):
            overrides = {
                "variables": {
                    "PublicSubnets": "1",
                    "SshKeyName": "1",
                    "PrivateSubnets": "1",
                    "Random": "${noop something}",
                },
                "requires": requires,
            }

            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=self.context)
            requires = [stack.fqn]

            steps += [Step(stack, None)]

        plan = build_plan(description="Test", steps=steps)

        tmp_dir = tempfile.mkdtemp()
        try:
            plan.dump(tmp_dir, context=self.context)

            for step in plan.steps:
                template_path = os.path.join(
                    tmp_dir,
                    stack_template_key_name(step.stack.blueprint))
                self.assertTrue(os.path.isfile(template_path))
        finally:
            shutil.rmtree(tmp_dir)
