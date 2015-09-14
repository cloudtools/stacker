from collections import namedtuple
import unittest

import mock

from stacker.actions import build
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

    def test_resolve_parameters_referencing_non_existant_output(self):
        parameters = {
            'param_1': 'mock::output_1',
            'param_2': 'other::does_not_exist',
        }
        self.build_action.provider.set_outputs({
            self.context.get_fqn('mock'): {'output_1': 'output'},
            self.context.get_fqn('other'): {},
        })
        mock_blueprint = mock.MagicMock()
        type(mock_blueprint).parameters = parameters
        with self.assertRaises(exceptions.OutputDoesNotExist):
            self.build_action._resolve_parameters(parameters,
                                                  mock_blueprint)

    def test_resolve_parameters(self):
        parameters = {
            'param_1': 'mock::output_1',
            'param_2': 'other::output_2',
        }
        self.build_action.provider.set_outputs({
            self.context.get_fqn('mock'): {'output_1': 'output1'},
            self.context.get_fqn('other'): {'output_2': 'output2'},
        })

        mock_blueprint = mock.MagicMock()
        type(mock_blueprint).parameters = parameters
        resolved_parameters = self.build_action._resolve_parameters(
            parameters,
            mock_blueprint,
        )
        self.assertEqual(resolved_parameters['param_1'], 'output1')
        self.assertEqual(resolved_parameters['param_2'], 'output2')

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
            # initial run should return SUBMITTED since we've passed off to CF
            status = step.run()
            self.assertEqual(status, SUBMITTED)

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
            # simulate completed stack
            mock_provider.is_stack_completed.return_value = True
            mock_provider.is_stack_in_progress.return_value = False
            status = step.run()
            self.assertEqual(status, COMPLETE)
            # simulate stack should be skipped
            mock_provider.is_stack_completed.return_value = False
            mock_provider.is_stack_in_progress.return_value = False
            mock_provider.update_stack.side_effect = StackDidNotChange
            status = step.run()
            self.assertEqual(status, SKIPPED)

            # simulate an update is required
            mock_provider.reset_mock()
            mock_provider.update_stack.side_effect = None
            step.set_status(PENDING)
            status = step.run()
            self.assertEqual(status, SUBMITTED)
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
