from collections import namedtuple
import unittest

import mock

from stacker.actions import build
from stacker.context import Context
from stacker import exceptions


Parameter = namedtuple('Parameter', ['key', 'value'])


class MockStack(object):
    def __init__(self, parameters):
        self.parameters = []
        for k, v in parameters.items():
            self.parameters.append(Parameter(key=k, value=v))


class TestBuildAction(unittest.TestCase):

    def setUp(self):
        self.context = Context('namespace')
        self.build_action = build.Action(self.context)

    def test_resolve_parameters_referencing_non_existant_output(self):
        parameters = {
            'param_1': 'mock::output_1',
            'param_2': 'other::does_not_exist',
        }
        outputs = {'mock': {'output_1': 'output'}, 'other': {}}
        mock_blueprint = mock.MagicMock()
        type(mock_blueprint).parameters = parameters
        with self.assertRaises(exceptions.ParameterDoesNotExist):
            self.build_action._resolve_parameters(outputs, parameters, mock_blueprint)

    def test_resolve_parameters_referencing_non_existant_stack(self):
        parameters = {
            'param_1': 'mock::output_1',
        }
        outputs = {}
        mock_blueprint = mock.MagicMock()
        type(mock_blueprint).parameters = parameters
        with self.assertRaises(exceptions.StackDoesNotExist):
            self.build_action._resolve_parameters(outputs, parameters, mock_blueprint)

    def test_gather_missing_from_stack(self):
        stack_params = {'Address': '10.0.0.1'}
        stack = MockStack(stack_params)
        def_params = {}
        required = ['Address']
        self.assertEqual(
            self.build_action._handle_missing_parameters(def_params, required, stack),
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
        result = self.build_action._handle_missing_parameters(def_params, required, stack)
        self.assertEqual(result, def_params.items())

    def test_get_dependencies(self):
        config = {'stacks': [
            {'name': 'vpc'},
            {'name': 'bastion', 'parameters': {'test': 'vpc::something'}},
            {'name': 'db', 'parameters': {'test': 'vpc::something', 'else': 'bastion::something'}},
            {'name': 'other', 'parameters': {}}
        ]}
        context = Context('namespace', config=config)
        build_action = build.Action(context)
        dependencies = build_action._get_dependencies()
        self.assertEqual(dependencies['bastion'], set(['vpc']))
        self.assertEqual(dependencies['db'], set(['vpc', 'bastion']))
        self.assertFalse(dependencies['other'])

    def test_get_stack_execution_order(self):
        config = {'stacks': [
            {'name': 'vpc'},
            {'name': 'bastion', 'parameters': {'test': 'vpc::something'}},
            {'name': 'db', 'parameters': {'test': 'vpc::something', 'else': 'bastion::something'}},
            {'name': 'other', 'parameters': {}}
        ]}
        context = Context('namespace', config=config)
        build_action = build.Action(context)
        dependencies = build_action._get_dependencies()
        execution_order = build_action.get_stack_execution_order(dependencies)
        self.assertEqual(execution_order, ['other', 'vpc', 'bastion', 'db'])

    def test_generate_plan(self):
        config = {'stacks': [
            {'name': 'vpc'},
            {'name': 'bastion', 'parameters': {'test': 'vpc::something'}},
            {'name': 'db', 'parameters': {'test': 'vpc::something', 'else': 'bastion::something'}},
            {'name': 'other', 'parameters': {}}
        ]}
        context = Context('namespace', config=config)
        build_action = build.Action(context)
        plan = build_action._generate_plan()
        self.assertEqual(plan.keys(), ['other', 'vpc', 'bastion', 'db'])
