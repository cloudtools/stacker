from collections import namedtuple
import unittest

import mock

from stacker.actions import build
from stacker.actions.build import resolve_parameters
from stacker.context import Context
from stacker import exceptions
from stacker.plan import COMPLETE, PENDING, SKIPPED, SUBMITTED
from stacker.exceptions import StackDidNotChange
from stacker.providers.base import BaseProvider


Parameter = namedtuple('Parameter', ['key', 'value'])


class MockStack(object):
    def __init__(self, parameters):
        self.parameters = []
        for k, v in parameters.items():
            self.parameters.append(Parameter(key=k, value=v))


class TestProvider(BaseProvider):
    def __init__(self, outputs=None, *args, **kwargs):
        self._outputs = outputs or {}

    def set_outputs(self, outputs):
        self._outputs = outputs

    def get_stack(self, stack_name, **kwargs):
        if stack_name not in self._outputs:
            raise exceptions.StackDoesNotExist(stack_name)
        return {'name': stack_name, 'outputs': self._outputs[stack_name]}

    def get_outputs(self, stack_name, *args, **kwargs):
        stack = self.get_stack(stack_name)
        return stack['outputs']


class TestBuildAction(unittest.TestCase):

    def setUp(self):
        self.context = Context({'namespace': 'namespace'})
        self.build_action = build.Action(self.context, provider=TestProvider())

    def _get_context(self, **kwargs):
        config = {'stacks': [
            {'name': 'vpc'},
            {'name': 'bastion', 'parameters': {'test': 'vpc::something'}},
            {'name': 'db', 'parameters': {'test': 'vpc::something',
             'else': 'bastion::something'}},
            {'name': 'other', 'parameters': {}}
        ]}
        return Context({'namespace': 'namespace'}, config=config, **kwargs)

    def test_resolve_parameters_referencing_non_existant_stack(self):
        parameters = {
            'param_1': 'mock::output_1',
        }
        self.build_action.provider.set_outputs({})
        mock_blueprint = mock.MagicMock()
        type(mock_blueprint).parameters = parameters
        with self.assertRaises(exceptions.StackDoesNotExist):
            self.build_action._resolve_parameters(parameters,
                                                  mock_blueprint)

    def test_gather_missing_from_stack(self):
        stack_params = {'Address': '10.0.0.1'}
        stack = MockStack(stack_params)
        def_params = {}
        required = ['Address']
        self.assertEqual(
            self.build_action._handle_missing_parameters(def_params, required,
                                                         stack),
            stack_params.items())

    def test_missing_params_no_stack(self):
        params = {}
        required = ['Address']
        with self.assertRaises(exceptions.MissingParameterException) as cm:
            self.build_action._handle_missing_parameters(params, required)

        self.assertEqual(cm.exception.parameters, required)

    def test_stack_params_dont_override_given_params(self):
        stack_params = {'Address': '10.0.0.1'}
        stack = MockStack(stack_params)
        def_params = {'Address': '192.168.0.1'}
        required = ['Address']
        result = self.build_action._handle_missing_parameters(def_params,
                                                              required, stack)
        self.assertEqual(result, def_params.items())

    def test_get_dependencies(self):
        context = self._get_context()
        build_action = build.Action(context)
        dependencies = build_action._get_dependencies()
        self.assertEqual(
            dependencies[context.get_fqn('bastion')],
            set([context.get_fqn('vpc')]),
        )
        self.assertEqual(
            dependencies[context.get_fqn('db')],
            set([context.get_fqn(s) for s in['vpc', 'bastion']]),
        )
        self.assertFalse(dependencies[context.get_fqn('other')])

    def test_get_stack_execution_order(self):
        context = self._get_context()
        build_action = build.Action(context)
        dependencies = build_action._get_dependencies()
        execution_order = build_action.get_stack_execution_order(dependencies)
        self.assertEqual(
            execution_order,
            [context.get_fqn(s) for s in ['other', 'vpc', 'bastion', 'db']],
        )

    def test_generate_plan(self):
        context = self._get_context()
        build_action = build.Action(context)
        plan = build_action._generate_plan()
        self.assertEqual(
            plan.keys(),
            [context.get_fqn(s) for s in ['other', 'vpc', 'bastion', 'db']],
        )

    def test_dont_execute_plan_when_outline_specified(self):
        context = self._get_context()
        build_action = build.Action(context)
        with mock.patch.object(build_action, '_generate_plan') as \
                mock_generate_plan:
            build_action.run(outline=True)
            self.assertEqual(mock_generate_plan().execute.call_count, 0)

    def test_execute_plan_when_outline_not_specified(self):
        context = self._get_context()
        build_action = build.Action(context)
        with mock.patch.object(build_action, '_generate_plan') as \
                mock_generate_plan:
            build_action.run(outline=False)
            self.assertEqual(mock_generate_plan().execute.call_count, 1)

    def test_launch_stack_step_statuses(self):
        mock_provider = mock.MagicMock()
        mock_stack = mock.MagicMock()

        context = self._get_context()
        build_action = build.Action(context, provider=mock_provider)
        plan = build_action._generate_plan()
        _, step = plan.list_pending()[0]
        step.stack = mock.MagicMock()
        step.stack.locked = False

        # mock provider shouldn't return a stack at first since it hasn't been
        # launched
        mock_provider.get_stack.return_value = None
        with mock.patch.object(build_action, 's3_stack_push'):
            # initial status should be PENDING
            self.assertEqual(step.status, PENDING)
            # initial run should return SUBMITTED since we've passed off to CF
            status = step.run()
            step.set_status(status)
            self.assertEqual(status, SUBMITTED)
            self.assertEqual(status.reason, "creating new stack")

            # provider should now return the CF stack since it exists
            mock_provider.get_stack.return_value = mock_stack
            # simulate that we're still in progress
            mock_provider.is_stack_in_progress.return_value = True
            mock_provider.is_stack_completed.return_value = False
            status = step.run()
            step.set_status(status)
            # status should still be SUBMITTED since we're waiting for it to
            # complete
            self.assertEqual(status, SUBMITTED)
            self.assertEqual(status.reason, "creating new stack")
            # simulate completed stack
            mock_provider.is_stack_completed.return_value = True
            mock_provider.is_stack_in_progress.return_value = False
            status = step.run()
            step.set_status(status)
            self.assertEqual(status, COMPLETE)
            self.assertEqual(status.reason, "creating new stack")

            # simulate stack should be skipped
            mock_provider.is_stack_completed.return_value = False
            mock_provider.is_stack_in_progress.return_value = False
            mock_provider.update_stack.side_effect = StackDidNotChange
            status = step.run()
            step.set_status(status)
            self.assertEqual(status, SKIPPED)
            self.assertEqual(status.reason, "nochange")

            # simulate an update is required
            mock_provider.reset_mock()
            mock_provider.update_stack.side_effect = None
            step.set_status(PENDING)
            status = step.run()
            step.set_status(status)
            self.assertEqual(status, SUBMITTED)
            self.assertEqual(status.reason, "updating existing stack")
            self.assertEqual(mock_provider.update_stack.call_count, 1)

    def test_should_update(self):
        test_scenario = namedtuple('test_scenario',
                                   ['locked', 'force', 'result'])
        test_scenarios = (
            test_scenario(locked=False, force=False, result=True),
            test_scenario(locked=False, force=True, result=True),
            test_scenario(locked=True, force=False, result=False),
            test_scenario(locked=True, force=True, result=True)
        )
        mock_stack = mock.MagicMock(["locked", "force", "name"])
        mock_stack.name = "test-stack"
        for t in test_scenarios:
            mock_stack.locked = t.locked
            mock_stack.force = t.force
            self.assertEqual(build.should_update(mock_stack), t.result)

    def test_should_submit(self):
        test_scenario = namedtuple('test_scenario',
                                   ['enabled', 'result'])
        test_scenarios = (
            test_scenario(enabled=False, result=False),
            test_scenario(enabled=True, result=True),
        )

        mock_stack = mock.MagicMock(["enabled", "name"])
        mock_stack.name = "test-stack"
        for t in test_scenarios:
            mock_stack.enabled = t.enabled
            self.assertEqual(build.should_submit(mock_stack), t.result)


class TestFunctions(unittest.TestCase):
    """ test module level functions """

    def setUp(self):
        self.ctx = Context({'namespace': 'test'})
        self.prov = mock.MagicMock()
        self.bp = mock.MagicMock()

    def test_resolve_parameters_unused_parameter(self):
        self.bp.parameters = {
            "a": {
                "type": "String",
                "description": "A"},
            "b": {
                "type": "String",
                "description": "B"
                }}
        params = {"a": "Apple", "c": "Carrot"}
        p = resolve_parameters(params, self.bp, self.ctx, self.prov)
        self.assertNotIn("c", p)
        self.assertIn("a", p)

    def test_resolve_parameters_none_conversion(self):
        self.bp.parameters = {
            "a": {
                "type": "String",
                "description": "A"},
            "b": {
                "type": "String",
                "description": "B"
                }}
        params = {"a": None, "c": "Carrot"}
        p = resolve_parameters(params, self.bp, self.ctx, self.prov)
        self.assertNotIn("a", p)

    def test_resolve_parameters_resolve_outputs(self):
        self.bp.parameters = {
            "a": {
                "type": "String",
                "description": "A"},
            "b": {
                "type": "String",
                "description": "B"
                }}
        params = {"a": "other-stack::a", "b": "Banana"}
        self.prov.get_output.return_value = "Apple"
        p = resolve_parameters(params, self.bp, self.ctx, self.prov)
        kall = self.prov.get_output.call_args
        args, kwargs = kall
        self.assertTrue(args[0], "test-other-stack")
        self.assertTrue(args[1], "a")
        self.assertEqual(p["a"], "Apple")
        self.assertEqual(p["b"], "Banana")

    def test_resolve_parameters_multiple_outputs(self):
        def get_output(stack, param):
            d = {'a': 'Apple', 'c': 'Carrot'}
            return d[param]

        self.bp.parameters = {
            "a": {
                "type": "String",
                "description": "A"},
            "b": {
                "type": "String",
                "description": "B"
                }}
        params = {"a": "other-stack::a,other-stack::c", "b": "Banana"}
        self.prov.get_output.side_effect = get_output
        p = resolve_parameters(params, self.bp, self.ctx, self.prov)
        self.assertEqual(self.prov.get_output.call_count, 2)
        self.assertEqual(p["a"], "Apple,Carrot")
        self.assertEqual(p["b"], "Banana")

    def test_resolve_parameters_output_does_not_exist(self):
        def get_output(stack, param):
            d = {'c': 'Carrot'}
            return d[param]

        self.bp.parameters = {
            "a": {
                "type": "String",
                "description": "A"
            },
        }
        params = {"a": "other-stack::a"}
        self.prov.get_output.side_effect = get_output
        with self.assertRaises(exceptions.OutputDoesNotExist) as cm:
            resolve_parameters(params, self.bp, self.ctx, self.prov)

        exc = cm.exception
        self.assertEqual(exc.stack_name, "test-other-stack")
        # Not sure this is actually what we want - should probably change it
        # so the output is just the output name, not the stack name + the
        # output name
        self.assertEqual(exc.output, "other-stack::a")

    def test_resolve_parameters_booleans(self):
        self.bp.parameters = {
            "a": {
                "type": "String",
                "description": "A"},
            "b": {
                "type": "String",
                "description": "B"},
        }
        params = {"a": True, "b": False}
        p = resolve_parameters(params, self.bp, self.ctx, self.prov)
        self.assertEquals("true", p["a"])
        self.assertEquals("false", p["b"])
