import unittest

from mock import MagicMock
from stacker.blueprints.base import (
    Blueprint,
    build_parameter,
    get_local_parameters,
    resolve_string,
    resolve,
)
from stacker.exceptions import (
    MissingLocalParameterException,
    UnresolvedBlueprintParameters,
)


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


class TestBlueprintParameters(unittest.TestCase):

    def test_defined_parameters(self):
        class TestBlueprint(Blueprint):
            BLUEPRINT_PARAMETERS = {
                "Param1": {"default": "default", "type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        self.assertEqual(
            blueprint.defined_parameters(),
            blueprint.BLUEPRINT_PARAMETERS,
        )

    def test_defined_parameters_subclass(self):
        class TestBlueprint(Blueprint):
            BLUEPRINT_PARAMETERS = {
                "Param1": {"default": 0, "type": int},
                "Param2": {"default": 0, "type": int},
            }

        class TestBlueprintSublcass(TestBlueprint):
            def defined_parameters(self):
                params = super(TestBlueprintSublcass, self).defined_parameters()
                params["Param2"]["default"] = 1
                params["Param3"] = {"default": 1, "type": int}
                return params

        blueprint = TestBlueprintSublcass(name="test", context=MagicMock())
        params = blueprint.defined_parameters()
        self.assertEqual(len(params.keys()), 3)
        self.assertEqual(params["Param2"]["default"], 1)

    def test_get_parameters_unresolved_parameters(self):
        class TestBlueprint(Blueprint):
            pass

        blueprint = TestBlueprint(name="test", context=MagicMock())
        with self.assertRaises(UnresolvedBlueprintParameters):
            blueprint.get_parameters()

    def test_resolve_parameters(self):
        class TestBlueprint(Blueprint):
            BLUEPRINT_PARAMETERS = {
                "Param1": {"default": 0, "type": int},
                "Param2": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        provider = MagicMock()
        context = MagicMock()
        values = {"Param1": 1, "Param2": "other-stack::Output", "Param3": 3}
        provider.get_output.return_value = "Test Output"
        blueprint.resolve_parameters(values, provider, context)
        self.assertEqual(blueprint.resolved_parameters["Param1"], 1)
        self.assertEqual(blueprint.resolved_parameters["Param2"], "Test Output")
        self.assertIsNone(blueprint.resolved_parameters.get("Param3"))

    def test_resolve_parameters_template_string_syntax(self):
        class TestBlueprint(Blueprint):
            BLUEPRINT_PARAMETERS = {
                "Param1": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        provider = MagicMock()
        context = MagicMock()
        values = {
            "Param1": (
                "postgres://user:password@${some-stack::CName}/"
                "${other-stack::DBName}"
            )
        }
        provider.get_output.return_value = "test"
        blueprint.resolve_parameters(values, provider, context)
        parameters = blueprint.get_parameters()
        self.assertEqual(
            parameters["Param1"],
            "postgres://user:password@test/test",
        )

    def test_recursive_resolve_parameters(self):
        class TestBlueprint(Blueprint):
            BLUEPRINT_PARAMETERS = {
                "Param1": {"type": dict}
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        provider = MagicMock()
        context = MagicMock()
        values = {
            "Param1": {
                "level1": "other-stack::Output",
                "level2": {
                    "level3": "other-stack::Output",
                    "level4": [
                        "other-stack::Output",
                        "other-stack::Output",
                        "other-stack::Output",
                    ],
                    "level5": "other-stack::Output,other-stack2::Output",
                    "level6": {
                        "level7": "other-stack::Output",
                    },
                }
            },
        }
        output_value = "Test Output"
        provider.get_output.return_value = output_value
        blueprint.resolve_parameters(values, provider, context)
        parameters = blueprint.get_parameters()
        self.assertEqual(parameters["Param1"]["level1"], output_value)
        self.assertEqual(parameters["Param1"]["level2"]["level3"], output_value)
        for value in parameters["Param1"]["level2"]["level4"]:
            self.assertEqual(value, output_value)
            self.assertEqual(parameters["Param1"]["level2"]["level5"],
                             "%(output_value)s,%(output_value)s" %
                             {"output_value": output_value})
        self.assertEqual(parameters["Param1"]["level2"]["level6"]["level7"],
                         output_value)

    def test_get_parameters(self):
        class TestBlueprint(Blueprint):
            BLUEPRINT_PARAMETERS = {
                "Param1": {"type": int},
                "Param2": {"type": str},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        provider = MagicMock()
        context = MagicMock()
        values = {"Param1": 1, "Param2": "other-stack::Output"}
        provider.get_output.return_value = "Test Output"
        blueprint.resolve_parameters(values, provider, context)
        parameters = blueprint.get_parameters()
        self.assertEqual(parameters["Param1"], 1)
        self.assertEqual(parameters["Param2"], "Test Output")

    def test_resolve_string_comma_delmited_list(self):
        provider = MagicMock()
        context = MagicMock()
        provider.get_output.return_value = "Test Output"
        output = resolve_string("some-stack::Output, other-stack::Output",
                                provider, context)
        self.assertEqual(output, "Test Output, Test Output")

    def test_resolve_string(self):
        provider = MagicMock()
        context = MagicMock()
        provider.get_output.return_value = "Test Output"
        output = resolve_string("some-stack::Output", provider, context)
        self.assertEqual(output, "Test Output")

    def test_resolve_string_output_ref(self):
        provider = MagicMock()
        context = MagicMock()
        provider.get_output.return_value = "Test Output"
        output = resolve_string("some.template.here:${some-stack::Output}",
                                provider, context)
        self.assertEqual(output, "some.template.here:Test Output")

    def test_resolve_with_string(self):
        provider = MagicMock()
        context = MagicMock()
        provider.get_output.return_value = "Test Output"
        output = resolve("some.template.here:${some-stack::Output}", provider,
                         context)
        self.assertEqual(output, "some.template.here:Test Output")

    def test_resolve_with_list(self):
        provider = MagicMock()
        context = MagicMock()
        provider.get_output.return_value = "Test Output"
        output = resolve(["${some-stack::Output}"], provider, context)
        self.assertEqual(output, ["Test Output"])

    def test_resolve_with_dict(self):
        provider = MagicMock()
        context = MagicMock()
        provider.get_output.return_value = "Test Output"
        output = resolve({"output": "${some-stack::Output}"}, provider, context)
        self.assertEqual(output, {"output": "Test Output"})
