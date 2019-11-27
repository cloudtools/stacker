from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import range
import json
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
    Graph,
    Plan,
    Step
)
from stacker.exceptions import (
    CancelExecution,
    GraphError,
    PersistentGraphLocked,
    PlanFailed
)
from stacker.status import (
    SUBMITTED,
    COMPLETE,
    SKIPPED,
    FAILED,
)
from stacker.stack import Stack

from .factories import generate_definition, mock_context

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

    def test_from_stack_name(self):
        """Return step from step name."""
        context = mock_context()
        stack_name = 'test-stack'
        result = Step.from_stack_name(stack_name, context)

        self.assertIsInstance(result, Step)
        self.assertEqual(stack_name, result.stack.name)

    def test_from_persistent_graph(self):
        """Return list of steps from graph dict."""
        context = mock_context()
        graph_dict = {
            'stack1': [],
            'stack2': ['stack1']
        }
        result = Step.from_persistent_graph(graph_dict, context)

        self.assertEqual(2, len(result))
        self.assertIsInstance(result, list)

        for step in result:
            self.assertIsInstance(step, Step)
            self.assertIn(step.stack.name, graph_dict.keys())


class TestGraph(unittest.TestCase):

    def setUp(self):
        self.context = mock_context()
        self.graph_dict = {
            'stack1': [],
            'stack2': ['stack1']
        }
        self.graph_dict_expected = {
            'stack1': set(),
            'stack2': set(['stack1'])
        }
        self.steps = Step.from_persistent_graph(self.graph_dict,
                                                self.context)

    def test_add_steps(self):
        graph = Graph()
        graph.add_steps(self.steps)

        self.assertEqual(self.steps, list(graph.steps.values()))
        self.assertEqual([step.name for step in self.steps],
                         list(graph.steps.keys()))
        self.assertEqual(self.graph_dict_expected, graph.to_dict())

    def test_pop(self):
        graph = Graph()
        graph.add_steps(self.steps)

        stack2 = next(step for step in self.steps if step.name == 'stack2')

        self.assertEqual(stack2, graph.pop(stack2))
        self.assertEqual({'stack1': set()}, graph.to_dict())

    def test_dumps(self):
        graph = Graph()
        graph.add_steps(self.steps)

        self.assertEqual(json.dumps(self.graph_dict), graph.dumps())

    def test_from_dict(self):
        graph = Graph.from_dict(self.graph_dict, self.context)

        self.assertIsInstance(graph, Graph)
        self.assertEqual([step.name for step in self.steps],
                         list(graph.steps.keys()))
        self.assertEqual(self.graph_dict_expected, graph.to_dict())

    def test_from_steps(self):
        graph = Graph.from_steps(self.steps)

        self.assertEqual(self.steps, list(graph.steps.values()))
        self.assertEqual([step.name for step in self.steps],
                         list(graph.steps.keys()))
        self.assertEqual(self.graph_dict_expected, graph.to_dict())


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

        graph = Graph.from_steps([
            Step(vpc, fn=None), Step(bastion, fn=None)])
        plan = Plan(description="Test", graph=graph)

        self.assertEqual(plan.graph.to_dict(), {
            'bastion.1': set(['vpc.1']),
            'vpc.1': set([])})

    def test_plan_reverse(self):
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=self.context)
        graph = Graph.from_steps([
            Step(vpc, fn=None), Step(bastion, fn=None)])
        plan = Plan(description="Test", graph=graph, reverse=True)

        # order is different between python2/3 so can't compare dicts
        result_graph_dict = plan.graph.to_dict()
        self.assertEqual(set(), result_graph_dict.get('bastion.1'))
        self.assertEqual(set(['bastion.1']), result_graph_dict.get('vpc.1'))

    def test_plan_targeted(self):
        context = Context(config=self.config)
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=context)
        context.stack_names = [vpc.name]
        graph = Graph.from_steps([
            Step(vpc, fn=None), Step(bastion, fn=None)])
        plan = Plan(description="Test", graph=graph, context=context)

        self.assertEqual({vpc.name: set()}, plan.graph.to_dict())

    def test_execute_plan(self):
        context = Context(config=self.config)
        context.put_persistent_graph = mock.MagicMock()
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=context)
        removed = Stack(
            definition=generate_definition('removed', 1, requires=[]),
            context=context)
        context._persistent_graph = Graph.from_steps([removed])

        calls = []

        def _launch_stack(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        def _destroy_stack(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        graph = Graph.from_steps([Step(removed, _destroy_stack),
                                  Step(vpc, _launch_stack),
                                  Step(bastion, _launch_stack)])
        plan = Plan(description="Test", graph=graph, context=context)
        plan.context._persistent_graph_lock_code = plan.lock_code
        plan.execute(walk)

        # the order these are appended changes between python2/3
        self.assertIn('namespace-vpc.1', calls)
        self.assertIn('namespace-bastion.1', calls)
        self.assertIn('namespace-removed.1', calls)
        context.put_persistent_graph.assert_called()

        # order is different between python2/3 so can't compare dicts
        result_graph_dict = context.persistent_graph.to_dict()
        self.assertEqual(2, len(result_graph_dict))
        self.assertEqual(set(), result_graph_dict.get('vpc.1'))
        self.assertEqual(set(['vpc.1']), result_graph_dict.get('bastion.1'))
        self.assertIsNone(result_graph_dict.get('namespace-removed.1'))

    def test_execute_plan_no_persist(self):
        context = Context(config=self.config)
        context.put_persistent_graph = mock.MagicMock()
        vpc = Stack(
            definition=generate_definition('vpc', 1),
            context=context)
        bastion = Stack(
            definition=generate_definition('bastion', 1, requires=[vpc.name]),
            context=context)

        calls = []

        def _launch_stack(stack, status=None):
            calls.append(stack.fqn)
            return COMPLETE

        graph = Graph.from_steps([Step(vpc, _launch_stack),
                                  Step(bastion, _launch_stack)])
        plan = Plan(description="Test", graph=graph, context=context)

        plan.execute(walk)

        self.assertEqual(calls, ['namespace-vpc.1', 'namespace-bastion.1'])
        context.put_persistent_graph.assert_not_called()

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

        context = mock.MagicMock()
        context.persistent_graph_locked = False
        context.stack_names = ['db.1']
        graph = Graph.from_steps([
            Step(vpc, fn), Step(db, fn), Step(app, fn)])
        plan = Plan(
            context=context,
            description="Test",
            graph=graph)
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

        graph = Graph.from_steps([vpc_step, bastion_step])
        plan = Plan(description="Test", graph=graph)

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

        graph = Graph.from_steps([vpc_step, bastion_step])
        plan = Plan(description="Test", graph=graph)
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

        graph = Graph.from_steps([
            vpc_step, bastion_step, db_step])
        plan = Plan(description="Test", graph=graph)
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

        graph = Graph.from_steps([vpc_step, bastion_step])
        plan = Plan(description="Test", graph=graph)
        plan.execute(walk)

        self.assertEquals(calls, ['namespace-vpc.1', 'namespace-bastion.1'])

    def test_execute_plan_locked(self):
        context = Context(config=self.config)
        context._persistent_graph = Graph.from_dict({'stack1': []}, context)
        context._persistent_graph_lock_code = '1111'
        plan = Plan(description='Test', graph=Graph(), context=context)
        print(plan.locked)

        with self.assertRaises(PersistentGraphLocked):
            plan.execute()

    def test_build_graph_missing_dependency(self):
        bastion = Stack(
            definition=generate_definition(
                'bastion', 1, requires=['vpc.1']),
            context=self.context)

        with self.assertRaises(GraphError) as expected:
            Graph.from_steps([Step(bastion, None)])
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
            Graph.from_steps([Step(vpc, None), Step(db, None),
                              Step(app, None)])
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

        graph = Graph.from_steps(steps)
        plan = Plan(description="Test", graph=graph)

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
