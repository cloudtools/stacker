import unittest

from mock import MagicMock
from troposphere import Ref

from stacker.blueprints.base import (
    Blueprint,
    CFNParameter,
    build_parameter,
    get_local_parameters,
)
from stacker.blueprints.variables.types import (
    CFNString,
    EC2AvailabilityZoneNameList,
)
from stacker.exceptions import (
    MissingLocalParameterException,
    MissingVariable,
    UnresolvedVariables,
)
from stacker.lookups import Lookup
from stacker.variables import Variable


class TestLocalParameters(unittest.TestCase):
    def test_default_parameter(self):
        parameter_def = {"Param1": {"default": 0}}
        parameters = {}

        local = get_local_parameters(parameter_def, parameters)
        self.assertEquals(local["Param1"], 0)

    def test_missing_required(self):
        parameter_def = {"Param1": {"default": 0}, "Param2": {}}
        parameters = {}

        with self.assertRaises(MissingLocalParameterException) as cm:
            get_local_parameters(parameter_def, parameters)

        self.assertEquals("Param2", cm.exception.parameter)

    def test_supplied_parameter(self):
        parameter_def = {"Param1": {"default": 0}, "Param2": {}}
        parameters = {"Param1": 1, "Param2": 2}

        local = get_local_parameters(parameter_def, parameters)
        self.assertEquals(parameters, local)


class TestBuildParameter(unittest.TestCase):
    def test_base_parameter(self):
        p = build_parameter("BasicParam", {"type": "String"})
        p.validate()
        self.assertEquals(p.Type, "String")


class TestVariables(unittest.TestCase):

    def test_defined_variables(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"default": "default", "type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        self.assertEqual(
            blueprint.defined_variables(),
            blueprint.VARIABLES,
        )

    def test_defined_variables_subclass(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"default": 0, "type": int},
                "Param2": {"default": 0, "type": int},
            }

        class TestBlueprintSublcass(TestBlueprint):
            def defined_variables(self):
                variables = super(TestBlueprintSublcass,
                                  self).defined_variables()
                variables["Param2"]["default"] = 1
                variables["Param3"] = {"default": 1, "type": int}
                return variables

        blueprint = TestBlueprintSublcass(name="test", context=MagicMock())
        variables = blueprint.defined_variables()
        self.assertEqual(len(variables.keys()), 3)
        self.assertEqual(variables["Param2"]["default"], 1)

    def test_get_variables_unresolved_variables(self):
        class TestBlueprint(Blueprint):
            pass

        blueprint = TestBlueprint(name="test", context=MagicMock())
        with self.assertRaises(UnresolvedVariables):
            blueprint.get_variables()

    def test_resolve_variables(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"default": 0, "type": int},
                "Param2": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [
            Variable("Param1", 1),
            Variable("Param2", "${other-stack::Output}"),
            Variable("Param3", 3),
        ]
        lookup = Lookup("other-stack", "Output", "other-stack::Output")
        resolved_lookups = {lookup: "Test Output"}
        for var in variables:
            var.replace(resolved_lookups)

        blueprint.resolve_variables(variables)
        self.assertEqual(blueprint.resolved_variables["Param1"], 1)
        self.assertEqual(blueprint.resolved_variables["Param2"], "Test Output")
        self.assertIsNone(blueprint.resolved_variables.get("Param3"))

    def test_get_variables(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int},
                "Param2": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", 1), Variable("Param2", "Test Output")]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertEqual(variables["Param1"], 1)
        self.assertEqual(variables["Param2"], "Test Output")

    def test_resolve_variables_missing_variable(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int},
                "Param2": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", 1)]
        with self.assertRaises(MissingVariable):
            blueprint.resolve_variables(variables)

    def test_resolve_variables_incorrect_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", "Something")]
        with self.assertRaises(ValueError):
            blueprint.resolve_variables(variables)

    def test_get_variables_default_value(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int, "default": 1},
                "Param2": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param2", "Test Output")]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertEqual(variables["Param1"], 1)
        self.assertEqual(variables["Param2"], "Test Output")

    def test_resolve_variables_convert_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", "1")]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertTrue(isinstance(variables["Param1"], int))

    def test_resolve_variables_cfn_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", "Value")]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertTrue(isinstance(variables["Param1"], CFNParameter))

    def test_resolve_variables_cfn_type_list(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": EC2AvailabilityZoneNameList},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", ["us-east-1", "us-west-2"])]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertTrue(isinstance(variables["Param1"], CFNParameter))
        self.assertEqual(variables["Param1"].value, ["us-east-1", "us-west-2"])
        self.assertEqual(variables["Param1"].ref.data, Ref("Param1").data)
        parameters = blueprint.get_cfn_parameters()
        self.assertEqual(parameters["Param1"], ["us-east-1", "us-west-2"])

    def test_resolve_variables_cfn_type_list_invalid_value(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": EC2AvailabilityZoneNameList},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", {"main": "us-east-1"})]
        with self.assertRaises(ValueError):
            blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()

    def test_get_parameters_cfn_type_list(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": EC2AvailabilityZoneNameList},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        parameters = blueprint._get_parameters()
        self.assertTrue("Param1" in parameters)
        parameter = parameters["Param1"]
        self.assertEqual(parameter["type"],
                         "List<AWS::EC2::AvailabilityZone::Name>")

    def test_get_parameters_cfn_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        parameters = blueprint._get_parameters()
        self.assertTrue("Param1" in parameters)
        parameter = parameters["Param1"]
        self.assertEqual(parameter["type"], "String")

    def test_required_parameters_cfn_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        blueprint.setup_parameters()
        self.assertEqual(blueprint.required_parameters[0][0], "Param1")

    def test_get_cfn_parameters(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int},
                "Param2": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", "1"), Variable("Param2", "Value")]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertEqual(len(variables), 2)
        parameters = blueprint.get_cfn_parameters()
        self.assertEqual(len(parameters.keys()), 1)
        self.assertEqual(parameters["Param2"], "Value")
