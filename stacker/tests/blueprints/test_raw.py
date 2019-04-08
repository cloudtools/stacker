"""Test module for blueprint-from-raw-template module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import json
import unittest

from mock import MagicMock

from stacker.blueprints.raw import (
    get_template_params, get_template_path, RawTemplateBlueprint
)
from stacker.variables import Variable
from ..factories import mock_context


RAW_JSON_TEMPLATE_PATH = 'stacker/tests/fixtures/cfn_template.json'
RAW_YAML_TEMPLATE_PATH = 'stacker/tests/fixtures/cfn_template.yaml'
RAW_J2_TEMPLATE_PATH = 'stacker/tests/fixtures/cfn_template.json.j2'


def test_get_template_path_local_file(tmpdir):
    """Verify get_template_path finding a file relative to CWD."""

    template_path = tmpdir.join('cfn_template.json')
    template_path.ensure()

    with tmpdir.as_cwd():
        result = get_template_path('cfn_template.json')
        assert template_path.samefile(result)


def test_get_template_path_invalid_file(tmpdir):
    """Verify get_template_path with an invalid filename."""

    with tmpdir.as_cwd():
        assert get_template_path('cfn_template.json') is None


def test_get_template_path_file_in_syspath(tmpdir, monkeypatch):
    """Verify get_template_path with a file in sys.path.

    This ensures templates are able to be retrieved from remote packages.

    """

    template_path = tmpdir.join('cfn_template.json')
    template_path.ensure()

    monkeypatch.syspath_prepend(tmpdir)
    result = get_template_path(template_path.basename)
    assert template_path.samefile(result)


def test_get_template_params():
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

    assert get_template_params(template_dict) == template_params


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

    def test_j2_to_json(self):
        """Verify jinja2 template parsing."""
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
                        "Value": "dummy-bar-param1val-foo-1234"
                    }
                }
            },
            sort_keys=True,
            indent=4
        )
        blueprint = RawTemplateBlueprint(
            name="stack1",
            context=mock_context(
                extra_config_args={'stacks': [{'name': 'stack1',
                                               'template_path': 'unused',
                                               'variables': {
                                                   'Param1': 'param1val',
                                                   'bar': 'foo'}}]},
                environment={'foo': 'bar'}),
            raw_template_path=RAW_J2_TEMPLATE_PATH
        )
        blueprint.resolve_variables([Variable("Param1", "param1val"),
                                     Variable("bar", "foo")])
        self.assertEqual(
            expected_json,
            blueprint.to_json()
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
