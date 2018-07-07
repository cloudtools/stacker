from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
import sys
from mock import patch

from mock import MagicMock
from troposphere import (
    Base64,
    Ref,
    s3,
    sns
)

from stacker.blueprints.base import (
    Blueprint,
    CFNParameter,
    build_parameter,
    validate_allowed_values,
    validate_variable_type,
    resolve_variable,
    parse_user_data
)
from stacker.blueprints.variables.types import (
    CFNCommaDelimitedList,
    CFNNumber,
    CFNString,
    EC2AvailabilityZoneNameList,
    TroposphereType,
)
from stacker.exceptions import (
    InvalidLookupCombination,
    MissingVariable,
    UnresolvedVariable,
    UnresolvedVariables,
    ValidatorError,
    VariableTypeRequired,
    InvalidUserdataPlaceholder
)
from stacker.variables import Variable
from stacker.lookups import register_lookup_handler

from ..factories import mock_lookup, mock_context


def mock_lookup_handler(value, provider=None, context=None, fqn=False,
                        **kwargs):
    return value


register_lookup_handler("mock", mock_lookup_handler)


class TestBuildParameter(unittest.TestCase):

    def test_base_parameter(self):
        p = build_parameter("BasicParam", {"type": "String"})
        p.validate()
        self.assertEquals(p.Type, "String")


class TestBlueprintRendering(unittest.TestCase):

    def test_to_json(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"default": "default", "type": CFNString},
                "Param2": {"type": CFNNumber},
                "Param3": {"type": CFNCommaDelimitedList},
                "Param4": {"default": "foo", "type": str},
                "Param5": {"default": 5, "type": int}
            }

            def create_template(self):
                self.template.add_version('2010-09-09')
                self.template.add_description('TestBlueprint')

        expected_json = """{
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "TestBlueprint",
    "Parameters": {
        "Param1": {
            "Default": "default",
            "Type": "String"
        },
        "Param2": {
            "Type": "Number"
        },
        "Param3": {
            "Type": "CommaDelimitedList"
        }
    },
    "Resources": {}
}"""
        self.assertEqual(
            TestBlueprint(name="test", context=mock_context()).to_json(),
            expected_json,
        )


class TestBaseBlueprint(unittest.TestCase):
    def test_add_output(self):
        output_name = "MyOutput1"
        output_value = "OutputValue"

        class TestBlueprint(Blueprint):
            VARIABLES = {}

            def create_template(self):
                self.template.add_version('2010-09-09')
                self.template.add_description('TestBlueprint')
                self.add_output(output_name, output_value)

        bp = TestBlueprint(name="test", context=mock_context())
        bp.render_template()
        self.assertEqual(bp.template.outputs[output_name].properties["Value"],
                         output_value)


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
        self.assertEqual(len(variables), 3)
        self.assertEqual(variables["Param2"]["default"], 1)

    def test_get_variables_unresolved_variables(self):
        class TestBlueprint(Blueprint):
            pass

        blueprint = TestBlueprint(name="test", context=MagicMock())
        with self.assertRaises(UnresolvedVariables):
            blueprint.get_variables()

    def test_set_description(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"default": "default", "type": str},
            }

            def create_template(self):
                return

        description = "my blueprint description"
        context = mock_context()
        blueprint = TestBlueprint(name="test", context=context,
                                  description=description)
        blueprint.render_template()
        self.assertEquals(description, blueprint.template.description)

    def test_validate_variable_type_cfntype(self):
        var_name = "testVar"
        var_type = CFNString
        provided_value = "abc"
        value = validate_variable_type(var_name, var_type, provided_value)
        self.assertIsInstance(value, CFNParameter)

    def test_validate_variable_type_cfntype_none_value(self):
        var_name = "testVar"
        var_type = CFNString
        provided_value = None
        with self.assertRaises(ValueError):
            validate_variable_type(var_name, var_type, provided_value)

    def test_validate_variable_type_matching_type(self):
        var_name = "testVar"
        var_type = str
        provided_value = "abc"
        value = validate_variable_type(var_name, var_type, provided_value)
        self.assertEqual(value, provided_value)

    # This tests that validate_variable_type doesn't change the original value
    # even if it could.  IE: A string "1" shouldn't be valid for an int.
    # See: https://github.com/remind101/stacker/pull/266
    def test_strict_validate_variable_type(self):
        var_name = "testVar"
        var_type = int
        provided_value = "1"
        with self.assertRaises(ValueError):
            validate_variable_type(var_name, var_type, provided_value)

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

    def _resolve_troposphere_var(self, tpe, value, **kwargs):
        var_name = "testVar"
        var_def = {"type": TroposphereType(tpe, **kwargs)}
        provided_variable = Variable(var_name, value)
        blueprint_name = "testBlueprint"

        return resolve_variable(var_name, var_def, provided_variable,
                                blueprint_name)

    def test_resolve_variable_troposphere_type_resource_single(self):
        bucket_defs = {"MyBucket": {"BucketName": "some-bucket"}}
        bucket = self._resolve_troposphere_var(s3.Bucket, bucket_defs)

        self.assertTrue(isinstance(bucket, s3.Bucket))
        self.assertEqual(bucket.properties, bucket_defs[bucket.title])
        self.assertEqual(bucket.title, "MyBucket")

    def test_resolve_variable_troposphere_type_resource_optional(self):
        bucket = self._resolve_troposphere_var(s3.Bucket, None, optional=True)
        self.assertEqual(bucket, None)

    def test_resolve_variable_troposphere_type_value_blank_required(self):
        with self.assertRaises(ValidatorError):
            self._resolve_troposphere_var(s3.Bucket, None)

    def test_resolve_variable_troposphere_type_resource_many(self):
        bucket_defs = {
            "FirstBucket": {"BucketName": "some-bucket"},
            "SecondBucket": {"BucketName": "some-other-bucket"}
        }
        buckets = self._resolve_troposphere_var(s3.Bucket, bucket_defs,
                                                many=True)

        for bucket in buckets:
            self.assertTrue(isinstance(bucket, s3.Bucket))
            self.assertEqual(bucket.properties, bucket_defs[bucket.title])

    def test_resolve_variable_troposphere_type_resource_many_empty(self):
        buckets = self._resolve_troposphere_var(s3.Bucket, {}, many=True)
        self.assertEqual(buckets, [])

    def test_resolve_variable_troposphere_type_resource_fail(self):
        # Do this to silence the error reporting here:
        # https://github.com/cloudtools/troposphere/commit/dc8abd5c
        with open("/dev/null", "w") as devnull:
            _stderr = sys.stderr
            sys.stderr = devnull
            with self.assertRaises(ValidatorError):
                self._resolve_troposphere_var(s3.Bucket,
                                              {"MyBucket": {"BucketName": 1}})
            sys.stderr = _stderr

    def test_resolve_variable_troposphere_type_props_single(self):
        sub_defs = {"Endpoint": "test", "Protocol": "lambda"}
        # Note that sns.Subscription != sns.SubscriptionResource. The former
        # is a property type, the latter is a complete resource.
        sub = self._resolve_troposphere_var(sns.Subscription, sub_defs)

        self.assertTrue(isinstance(sub, sns.Subscription))
        self.assertEqual(sub.properties, sub_defs)

    def test_resolve_variable_troposphere_type_props_optional(self):
        sub = self._resolve_troposphere_var(sns.Subscription, None,
                                            optional=True)
        self.assertEqual(sub, None)

    def test_resolve_variable_troposphere_type_props_many(self):
        sub_defs = [
            {"Endpoint": "test1", "Protocol": "lambda"},
            {"Endpoint": "test2", "Protocol": "lambda"}
        ]
        subs = self._resolve_troposphere_var(sns.Subscription, sub_defs,
                                             many=True)

        for i, sub in enumerate(subs):
            self.assertTrue(isinstance(sub, sns.Subscription))
            self.assertEqual(sub.properties, sub_defs[i])

    def test_resolve_variable_troposphere_type_props_many_empty(self):
        subs = self._resolve_troposphere_var(sns.Subscription, [], many=True)
        self.assertEqual(subs, [])

    def test_resolve_variable_troposphere_type_props_fail(self):
        with self.assertRaises(ValidatorError):
            self._resolve_troposphere_var(sns.Subscription, {})

    def test_resolve_variable_troposphere_type_unvalidated(self):
        self._resolve_troposphere_var(sns.Subscription, {}, validate=False)

    def test_resolve_variable_troposphere_type_optional_many(self):
        res = self._resolve_troposphere_var(sns.Subscription, {},
                                            many=True, optional=True)
        self.assertIsNone(res)

    def test_resolve_variable_provided_resolved(self):
        var_name = "testVar"
        var_def = {"type": str}
        provided_variable = Variable(var_name, "${mock 1}")
        provided_variable.resolve(context=MagicMock(), provider=MagicMock())
        blueprint_name = "testBlueprint"

        value = resolve_variable(var_name, var_def, provided_variable,
                                 blueprint_name)
        self.assertEqual(value, "1")

    def test_resolve_variable_allowed_values(self):
        var_name = "testVar"
        var_def = {"type": str, "allowed_values": ["allowed"]}
        provided_variable = Variable(var_name, "not_allowed")
        blueprint_name = "testBlueprint"
        with self.assertRaises(ValueError):
            resolve_variable(var_name, var_def, provided_variable,
                             blueprint_name)

        provided_variable = Variable(var_name, "allowed")
        value = resolve_variable(var_name, var_def, provided_variable,
                                 blueprint_name)
        self.assertEqual(value, "allowed")

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
            Variable("Param2", "${output other-stack::Output}"),
            Variable("Param3", 3),
        ]
        resolved_lookups = {
            mock_lookup("other-stack::Output", "output"): "Test Output",
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
                "${custom non-string-return-val},${output some-stack::Output}",
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
        variables = [Variable("Param1", 1)]
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
        self.assertEqual(list(params.keys())[0], "Param1")

    def test_get_parameter_values(self):
        class TestBlueprint(Blueprint):
            VARIABLES = {
                "Param1": {"type": int},
                "Param2": {"type": CFNString},
            }

        blueprint = TestBlueprint(name="test", context=MagicMock())
        variables = [Variable("Param1", 1), Variable("Param2", "Value")]
        blueprint.resolve_variables(variables)
        variables = blueprint.get_variables()
        self.assertEqual(len(variables), 2)
        parameters = blueprint.get_parameter_values()
        self.assertEqual(len(parameters), 1)
        self.assertEqual(parameters["Param2"], "Value")

    def test_validate_allowed_values(self):
        allowed_values = ['allowed']
        valid = validate_allowed_values(allowed_values, "not_allowed")
        self.assertFalse(valid)
        valid = validate_allowed_values(allowed_values, "allowed")
        self.assertTrue(valid)

    def test_blueprint_with_parameters_fails(self):
        class TestBlueprint(Blueprint):
            PARAMETERS = {
                "Param2": {"default": 0, "type": "Integer"},
            }

        with self.assertRaises(AttributeError):
            TestBlueprint(name="test", context=MagicMock())

        class TestBlueprint(Blueprint):
            LOCAL_PARAMETERS = {
                "Param2": {"default": 0, "type": "Integer"},
            }

        with self.assertRaises(AttributeError):
            TestBlueprint(name="test", context=MagicMock())

    def test_variable_exists_but_value_is_none(self):
        var_name = "testVar"
        var_def = {"type": str}
        var_value = None
        provided_variable = Variable(var_name, var_value)
        blueprint_name = "testBlueprint"

        with self.assertRaises(ValueError):
            resolve_variable(var_name, var_def, provided_variable,
                             blueprint_name)


class TestCFNParameter(unittest.TestCase):
    def test_cfnparameter_convert_boolean(self):
        p = CFNParameter("myParameter", True)
        self.assertEqual(p.value, "true")
        p = CFNParameter("myParameter", False)
        self.assertEqual(p.value, "false")
        # Test to make sure other types aren't affected
        p = CFNParameter("myParameter", 0)
        self.assertEqual(p.value, "0")
        p = CFNParameter("myParameter", "myString")
        self.assertEqual(p.value, "myString")

    def test_parse_user_data(self):
        expected = 'name: tom, last: taubkin and $'
        variables = {
            'name': 'tom',
            'last': 'taubkin'
        }

        raw_user_data = 'name: ${name}, last: $last and $$'
        blueprint_name = 'test'
        res = parse_user_data(variables, raw_user_data, blueprint_name)
        self.assertEqual(res, expected)

    def test_parse_user_data_missing_variable(self):
        variables = {
            'name': 'tom',
        }

        raw_user_data = 'name: ${name}, last: $last and $$'
        blueprint_name = 'test'
        with self.assertRaises(MissingVariable):
            parse_user_data(variables, raw_user_data, blueprint_name)

    def test_parse_user_data_invaled_placeholder(self):
        raw_user_data = '$100'
        blueprint_name = 'test'
        with self.assertRaises(InvalidUserdataPlaceholder):
            parse_user_data({}, raw_user_data, blueprint_name)

    @patch('stacker.blueprints.base.read_value_from_path',
           return_value='contents')
    @patch('stacker.blueprints.base.parse_user_data')
    def test_read_user_data(self, parse_mock, file_mock):
        class TestBlueprint(Blueprint):
            VARIABLES = {}

        blueprint = TestBlueprint(name="blueprint_name", context=MagicMock())
        blueprint.resolve_variables({})
        blueprint.read_user_data('file://test.txt')
        file_mock.assert_called_with('file://test.txt')
        parse_mock.assert_called_with({}, 'contents', 'blueprint_name')
