import unittest

from stacker.blueprints.base import get_local_parameters, build_parameter
from stacker.exceptions import MissingLocalParameterException


class TestLocalParameters(unittest.TestCase):
    def test_default_parameter(self):
        parameter_def = {'Param1': {'default': 0}}
        parameters = {}

        local = get_local_parameters(parameter_def, parameters)
        self.assertEquals(local['Param1'], 0)

    def test_missing_required(self):
        parameter_def = {'Param1': {'default': 0}, 'Param2': {}}
        parameters = {}

        with self.assertRaises(MissingLocalParameterException) as cm:
            get_local_parameters(parameter_def, parameters)

        self.assertEquals('Param2', cm.exception.parameter)

    def test_supplied_parameter(self):
        parameter_def = {'Param1': {'default': 0}, 'Param2': {}}
        parameters = {'Param1': 1, 'Param2': 2}

        local = get_local_parameters(parameter_def, parameters)
        self.assertEquals(parameters, local)


class TestBuildParameter(unittest.TestCase):
    def test_base_parameter(self):
        p = build_parameter("BasicParam", {'type': 'String'})
        p.validate()
        self.assertEquals(p.Type, 'String')
