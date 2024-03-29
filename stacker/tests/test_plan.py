import os
import shutil
import tempfile

import unittest
import mock

from stacker.context import Context, Config
from stacker.dag import walk
from stacker.util import stack_template_key_name
from stacker.lookups.registry import (
    register_lookup_handler,
    unregister_lookup_handler,
)
from stacker.plan import (
    Step,
    build_plan,
    build_graph,
)
from stacker.exceptions import (
    CancelExecution,
    GraphError,
    PlanFailed,
)
from stacker.status import (
    SUBMITTED,
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
        stack.name = "stack"
        stack.fqn = "namespace-stack"
        self.step = Step(stack=stack, fn=None)

    def test_status(self):
        self.assertFalse(self.step.submitted)
        self.assertFalse(self.step.completed)

        self.step.submit()
        self.assertEqual(self.step.status, SUBMITTED)
        self.assertTrue(self.step.submitted)
        self.assertFalse(self.step.completed)

        self.step.complete()
        self.assertEqual(self.step.status, COMPLETE)
        self.assertNotEqual(self.step.status, SUBMITTED)
        self.assertTrue(self.step.submitted)
        self.assertTrue(self.step.completed)

        self.assertNotEqual(self.step.status, True)
        self.assertNotEqual(self.step.status, False)
        self.assertNotEqual(self.step.status, 'banana')


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
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)

        graph = build_graph([
            Step(vpc, fn=None), Step(bastion, fn=None)])
        plan = build_plan(description="Test", graph=graph)

        self.assertEqual(plan.graph.to_dict(), {
            'bastion.1': set(['vpc.1']),
            'vpc.1': set([])})

    def test_execute_plan(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        graph = build_graph([Step(vpc, fn), Step(bastion, fn)])
        plan = build_plan(
            description="Test", graph=graph)
        plan.execute(walk)

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_locked(self):
        # Locked stacks still need to have their requires evaluated when
        # they're being created.
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            locked=True,
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        graph = build_graph([Step(vpc, fn), Step(bastion, fn)])
        plan = build_plan(
            description="Test", graph=graph)
        plan.execute(walk)

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_filtered(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        db = Stack(
            definition=generate_definition('db', 1, requires=[vpc.name]),
            context=self.context)
        app = Stack(
            definition=generate_definition('app', 1, requires=[db.name]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        graph = build_graph([
            Step(vpc, fn), Step(db, fn), Step(app, fn)])
        plan = build_plan(
            description="Test",
            graph=graph,
            targets=['db.1'])
        plan.execute(walk)

        self.assertEquals(calls, [
            'namespace-vpc.1', 'namespace-db.1'])

    def test_execute_plan_exception(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.name == vpc_step.name:
                raise ValueError('Boom')
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)

        graph = build_graph([vpc_step, bastion_step])
        plan = build_plan(description="Test", graph=graph)

        with self.assertRaises(PlanFailed):
            plan.execute(walk)

        self.assertEquals(calls, ['namespace-vpc.1'])
        self.assertEquals(vpc_step.status, FAILED)

    def test_execute_plan_skipped(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.fqn == vpc_step.name:
                return SKIPPED
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)

        graph = build_graph([vpc_step, bastion_step])
        plan = build_plan(description="Test", graph=graph)
        plan.execute(walk)

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_failed(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)
        db = Stack(
            definition=generate_definition('db', 1),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.name == vpc_step.name:
                return FAILED
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)
        db_step = Step(db, fn)

        graph = build_graph([
            vpc_step, bastion_step, db_step])
        plan = build_plan(description="Test", graph=graph)
        with self.assertRaises(PlanFailed):
            plan.execute(walk)

        calls.sort()

        self.assertEquals(calls, ['namespace-db.1', 'namespace-vpc.1'])

    def test_execute_plan_cancelled(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)

        calls = []

        def fn(stack, status=None):
            calls.append(stack.fqn)
            if stack.fqn == vpc_step.name:
                raise CancelExecution
            return COMPLETE

        vpc_step = Step(vpc, fn)
        bastion_step = Step(bastion, fn)

        graph = build_graph([vpc_step, bastion_step])
        plan = build_plan(description="Test", graph=graph)
        plan.execute(walk)

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_build_graph_missing_dependency(self):
        bastion = Stack(
            definition=generate_definition(
                'bastion', 1, requires=['vpc.1']),
            context=self.context)

        with self.assertRaises(GraphError) as expected:
            build_graph([Step(bastion, None)])
        message_starts = (
            "Error detected when adding 'vpc.1' "
            "as a dependency of 'bastion.1':"
        )
        message_contains = "dependent node vpc.1 does not exist"
        self.assertTrue(str(expected.exception).startswith(message_starts))
        self.assertTrue(message_contains in str(expected.exception))

    def test_build_graph_cyclic_dependencies(self):
        vpc = Stack(
            definition=generate_definition(
                'vpc', 1),
            context=self.context)
        db = Stack(
            definition=generate_definition(
                'db', 1, requires=['app.1']),
            context=self.context)
        app = Stack(
            definition=generate_definition(
                'app', 1, requires=['db.1']),
            context=self.context)

        with self.assertRaises(GraphError) as expected:
            build_graph([Step(vpc, None), Step(db, None), Step(app, None)])
        message = ("Error detected when adding 'db.1' "
                   "as a dependency of 'app.1': graph is "
                   "not acyclic")
        self.assertEqual(str(expected.exception), message)

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
            requires = [stack.name]

            steps += [Step(stack, None)]

        graph = build_graph(steps)
        plan = build_plan(description="Test", graph=graph)

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
