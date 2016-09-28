import unittest

from mock import MagicMock
from troposphere import (
    Base64,
    Ref,
)

from stacker.blueprints.base import (
    Blueprint,
    CFNParameter,
    build_parameter,
    validate_variable_type,
    resolve_variable
)
from stacker.blueprints.variables.types import (
    CFNNumber,
    CFNString,
    EC2AvailabilityZoneNameList,
)
from stacker.exceptions import (
    InvalidLookupCombination,
    MissingVariable,
    UnresolvedVariable,
    UnresolvedVariables,
    ValidatorError,
    VariableTypeRequired,
)
from stacker.variables import Variable
from stacker.lookups import register_lookup_handler

from ..factories import mock_lookup


def mock_lookup_handler(value, provider=None, context=None, fqn=False,
                        **kwargs):
    return value

register_lookup_handler("mock", mock_lookup_handler)


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

    def test_validate_variable_type_cfntype(self):
        var_name = "testVar"
        var_type = CFNString
        provided_value = "abc"
        value = validate_variable_type(var_name, var_type, provided_value)
        self.assertIsInstance(value, CFNParameter)
        self.assertEqual(value.value, provided_value)
        self.assertEqual(value.name, var_name)

    def test_validate_variable_type_matching_type(self):
        var_name = "testVar"
        var_type = str
        provided_value = "abc"
        value = validate_variable_type(var_name, var_type, provided_value)
        self.assertEqual(value, provided_value)

    def test_validate_variable_type_transformed_type(self):
        var_name = "testVar"
        var_type = int
        provided_value = "1"
        value = validate_variable_type(var_name, var_type, provided_value)
        self.assertEqual(value, int(provided_value))

    def test_validate_variable_type_invalid_value(self):
        var_name = "testVar"
        var_type = int
        provided_value = "abc"
        with self.assertRaises(ValueError):
            validate_variable_type(var_name, var_type, provided_value)

    def test_resolve_variable_no_type_on_variable_definition(self):
        var_name = "testVar"
        var_def = {}
        provided_variable = None
        blueprint_name = "testBlueprint"

        with self.assertRaises(VariableTypeRequired):
            resolve_variable(var_name, var_def, provided_variable,
                             blueprint_name)

    def test_resolve_variable_no_provided_with_default(self):
        var_name = "testVar"
        default_value = "foo"
        var_def = {"default": default_value, "type": str}
        provided_variable = None
        blueprint_name = "testBlueprint"

        value = resolve_variable(var_name, var_def, provided_variable,
                                 blueprint_name)

        self.assertEqual(default_value, value)

    def test_resolve_variable_no_provided_without_default(self):
        var_name = "testVar"
        var_def = {"type": str}
        provided_variable = None
        blueprint_name = "testBlueprint"

        with self.assertRaises(MissingVariable):
            resolve_variable(var_name, var_def, provided_variable,
                             blueprint_name)

    def test_resolve_variable_provided_not_resolved(self):
        var_name = "testVar"
        var_def = {"type": str}
        provided_variable = Variable(var_name, "${mock abc}")
        blueprint_name = "testBlueprint"

        with self.assertRaises(UnresolvedVariable):
            resolve_variable(var_name, var_def, provided_variable,
                             blueprint_name)

    def test_resolve_variable_provided_resolved(self):
        var_name = "testVar"
        var_def = {"type": str}
        provided_variable = Variable(var_name, "${mock 1}")
        provided_variable.resolve(context=MagicMock(), provider=MagicMock())
        blueprint_name = "testBlueprint"

        value = resolve_variable(var_name, var_def, provided_variable,
                                 blueprint_name)
        self.assertEqual(value, "1")

    def test_resolve_variable_validator_valid_value(self):
        def triple_validator(value):
            if len(value) != 3:
                raise ValueError
            return value

        var_name = "testVar"
        var_def = {"type": list, "validator": triple_validator}
        var_value = [1, 2, 3]
        provided_variable = Variable(var_name, var_value)
        blueprint_name = "testBlueprint"

        value = resolve_variable(var_name, var_def, provided_variable,
                                 blueprint_name)
        self.assertEqual(value, var_value)

    def test_resolve_variable_validator_invalid_value(self):
        def triple_validator(value):
            if len(value) != 3:
                raise ValueError("Must be a triple.")
            return value

        var_name = "testVar"
        var_def = {"type": list, "validator": triple_validator}
        var_value = [1, 2]
        provided_variable = Variable(var_name, var_value)
        blueprint_name = "testBlueprint"

        with self.assertRaises(ValidatorError) as cm:
            resolve_variable(var_name, var_def, provided_variable,
                             blueprint_name)

        exc = cm.exception.exception  # The wrapped exception
        self.assertIsInstance(exc, ValueError)

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
        resolved_lookups = {
            mock_lookup("other-stack::Output"): "Test Output",
        }
        for var in variables:
            var.replace(resolved_lookups)

        blueprint.resolve_variables(variables)
        self.assertEqual(blueprint.resolved_variables["Param1"], 1)
        self.assertEqual(blueprint.resolved_variables["Param2"], "Test Output")
        self.assertIsNone(blueprint.resolved_variables.get("Param3"))

    def test_resolve_variables_lookup_returns_non_string(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": list},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", "${custom non-string-return-val}")]
        lookup = mock_lookup("non-string-return-val", "custom",
                             "custom non-string-return-val")
        resolved_lookups = {
            lookup: ["something"],
        }
        for var in variables:
            var.replace(resolved_lookups)

        blueprint.resolve_variables(variables)
        self.assertEqual(blueprint.resolved_variables["Param1"], ["something"])

    def test_resolve_variables_lookup_returns_troposphere_obj(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": Base64},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", "${custom non-string-return-val}")]
        lookup = mock_lookup("non-string-return-val", "custom",
                             "custom non-string-return-val")
        resolved_lookups = {
            lookup: Base64("test"),
        }
        for var in variables:
            var.replace(resolved_lookups)

        blueprint.resolve_variables(variables)
        self.assertEqual(blueprint.resolved_variables["Param1"].data,
                         Base64("test").data)

    def test_resolve_variables_lookup_returns_non_string_invalid_combo(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": list},
            }

        variables = [
            Variable(
                "Param1",
                "${custom non-string-return-val},${some-stack::Output}",
            )
        ]
        lookup = mock_lookup("non-string-return-val", "custom",
                             "custom non-string-return-val")
        resolved_lookups = {
            lookup: ["something"],
        }
        with self.assertRaises(InvalidLookupCombination):
            for var in variables:
                var.replace(resolved_lookups)

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

    def test_resolve_variables_cfn_number(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": CFNNumber},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", 1)]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertTrue(isinstance(variables["Param1"], CFNParameter))
        self.assertEqual(variables["Param1"].value, "1")

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
        parameters = blueprint.get_parameter_values()
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

    def test_get_parameter_definitions_cfn_type_list(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": EC2AvailabilityZoneNameList},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        parameters = blueprint.get_parameter_definitions()
        self.assertTrue("Param1" in parameters)
        parameter = parameters["Param1"]
        self.assertEqual(parameter["type"],
                         "List<AWS::EC2::AvailabilityZone::Name>")

    def test_get_parameter_definitions_cfn_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        parameters = blueprint.get_parameter_definitions()
        self.assertTrue("Param1" in parameters)
        parameter = parameters["Param1"]
        self.assertEqual(parameter["type"], "String")

    def test_get_required_parameter_definitions_cfn_type(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        blueprint.setup_parameters()
        params = blueprint.get_required_parameter_definitions()
        self.assertEqual(params.keys()[0], "Param1")

    def test_get_parameter_values(self):
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
        parameters = blueprint.get_parameter_values()
        self.assertEqual(len(parameters.keys()), 1)
        self.assertEqual(parameters["Param2"], "Value")
