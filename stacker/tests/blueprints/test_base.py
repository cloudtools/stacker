import unittest

from mock import MagicMock
from stacker.blueprints.base import (
    Blueprint,
    build_parameter,
    get_local_parameters,
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
