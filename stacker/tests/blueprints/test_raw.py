"""Test module for blueprint-from-raw-template module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import json
import os
import sys
import unittest

from mock import MagicMock

from stacker.blueprints.raw import (
    get_template_params, get_template_path, RawTemplateBlueprint
)
from ..factories import mock_context

RAW_JSON_TEMPLATE_PATH = 'stacker/tests/fixtures/cfn_template.json'
RAW_YAML_TEMPLATE_PATH = 'stacker/tests/fixtures/cfn_template.yaml'


class TestRawBluePrintHelpers(unittest.TestCase):
    """Test class for functions in module."""

    def test_get_template_path_local_file(self):  # noqa pylint: disable=invalid-name
        """Verify get_template_path finding a file relative to CWD."""
        self.assertEqual(get_template_path(RAW_YAML_TEMPLATE_PATH),
                         RAW_YAML_TEMPLATE_PATH)

    def test_get_template_path_invalid_file(self):  # noqa pylint: disable=invalid-name
        """Verify get_template_path with an invalid filename."""
        self.assertEqual(get_template_path('afilenamethatdoesnotexist.txt'),
                         None)

    def test_get_template_path_file_in_syspath(self):  # noqa pylint: disable=invalid-name
        """Verify get_template_path with a file in sys.path.

        This ensures templates are able to be retreived from remote packages.

        """
        stacker_tests_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # noqa
        old_sys_path = list(sys.path)
        sys.path.append(stacker_tests_dir)
        try:
            self.assertEqual(get_template_path('fixtures/cfn_template.yaml'),
                             os.path.join(stacker_tests_dir,
                                          'fixtures/cfn_template.yaml'))
        finally:
            sys.path = old_sys_path

    def test_get_template_params(self):
        """Verify get_template_params function operation."""
        template_dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "TestTemplate",
            "Parameters": {
                "Param1": {
                    "Type": "String"
                },
                "Param2": {
                    "Default": "default",
                    "Type": "CommaDelimitedList"
                }
            },
            "Resources": {}
        }
        template_params = {
            "Param1": {
                "Type": "String"
            },
            "Param2": {
                "Default": "default",
                "Type": "CommaDelimitedList"
            }
        }
        self.assertEqual(get_template_params(template_dict), template_params)


class TestBlueprintRendering(unittest.TestCase):
    """Test class for blueprint rendering."""

    def test_to_json(self):
        """Verify to_json method operation."""
        expected_json = json.dumps(
            {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Description": "TestTemplate",
                "Parameters": {
                    "Param1": {
                        "Type": "String"
                    },
                    "Param2": {
                        "Default": "default",
                        "Type": "CommaDelimitedList"
                    }
                },
                "Resources": {
                    "Dummy": {
                        "Type": "AWS::CloudFormation::WaitConditionHandle"
                    }
                },
                "Outputs": {
                    "DummyId": {
                        "Value": "dummy-1234"
                    }
                }
            },
            sort_keys=True,
            indent=4
        )
        self.assertEqual(
            RawTemplateBlueprint(
                name="test",
                context=mock_context(),
                raw_template_path=RAW_JSON_TEMPLATE_PATH).to_json(),
            expected_json
        )


class TestVariables(unittest.TestCase):
    """Test class for blueprint variable methods."""

    def test_get_parameter_definitions_json(self):  # noqa pylint: disable=invalid-name
        """Verify get_parameter_definitions method with json raw template."""
        blueprint = RawTemplateBlueprint(
            name="test",
            context=MagicMock(),
            raw_template_path=RAW_JSON_TEMPLATE_PATH)
        parameters = blueprint.get_parameter_definitions()
        self.assertEqual(
            parameters,
            {"Param1": {"Type": "String"},
             "Param2": {"Default": "default",
                        "Type": "CommaDelimitedList"}})

    def test_get_parameter_definitions_yaml(self):  # noqa pylint: disable=invalid-name
        """Verify get_parameter_definitions method with yaml raw template."""
        blueprint = RawTemplateBlueprint(
            name="test",
            context=MagicMock(),
            raw_template_path=RAW_YAML_TEMPLATE_PATH
        )
        parameters = blueprint.get_parameter_definitions()
        self.assertEqual(
            parameters,
            {"Param1": {"Type": "String"},
             "Param2": {"Default": "default",
                        "Type": "CommaDelimitedList"}})

    def test_get_required_parameter_definitions_json(self):  # noqa pylint: disable=invalid-name
        """Verify get_required_param... method with json raw template."""
        blueprint = RawTemplateBlueprint(
            name="test",
            context=MagicMock(),
            raw_template_path=RAW_JSON_TEMPLATE_PATH
        )
        self.assertEqual(
            blueprint.get_required_parameter_definitions(),
            {"Param1": {"Type": "String"}})

    def test_get_required_parameter_definitions_yaml(self):  # noqa pylint: disable=invalid-name
        """Verify get_required_param... method with yaml raw template."""
        blueprint = RawTemplateBlueprint(
            name="test",
            context=MagicMock(),
            raw_template_path=RAW_YAML_TEMPLATE_PATH
        )
        self.assertEqual(
            blueprint.get_required_parameter_definitions(),
            {"Param1": {"Type": "String"}})
