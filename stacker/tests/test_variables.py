from mock import MagicMock
import unittest

from stacker.variables import Variable
from stacker.lookups import register_lookup_handler

from .factories import mock_lookup


class TestVariables(unittest.TestCase):

    def setUp(self):
        self.provider = MagicMock()
        self.context = MagicMock()

    def test_variable_replace_no_lookups(self):
        var = Variable("Param1", "2")
        self.assertEqual(len(var.lookups), 0)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, "2")

    def test_variable_resolve_no_lookups(self):
        var = Variable("Param1", "2")
        self.assertEqual(len(var.lookups), 0)
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "2")

    def test_variable_replace_simple_lookup(self):
        var = Variable("Param1", "${fakeStack::FakeOutput}")
        self.assertEqual(len(var.lookups), 1)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, "resolved")

    def test_variable_resolve_simple_lookup(self):
        var = Variable("Param1", "${fakeStack::FakeOutput}")
        self.assertEqual(len(var.lookups), 1)
        self.provider.get_output.return_value = "resolved"
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "resolved")

    def test_variable_replace_multiple_lookups_string(self):
        var = Variable(
            "Param1",
            "url://${fakeStack::FakeOutput}@${fakeStack::FakeOutput2}",
        )
        self.assertEqual(len(var.lookups), 2)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
            mock_lookup("fakeStack::FakeOutput2"): "resolved2",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, "url://resolved@resolved2")

    def test_variable_resolve_multiple_lookups_string(self):
        var = Variable(
            "Param1",
            "url://${fakeStack::FakeOutput}@${fakeStack::FakeOutput2}",
        )
        self.assertEqual(len(var.lookups), 2)

        def _get_output(fqn, output_name):
            outputs = {
                "FakeOutput": "resolved",
                "FakeOutput2": "resolved2",
            }
            return outputs[output_name]

        self.provider.get_output.side_effect = _get_output
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "url://resolved@resolved2")

    def test_variable_replace_no_lookups_list(self):
        var = Variable("Param1", ["something", "here"])
        self.assertEqual(len(var.lookups), 0)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, ["something", "here"])

    def test_variable_replace_lookups_list(self):
        value = ["something", "${fakeStack::FakeOutput}",
                 "${fakeStack::FakeOutput2}"]
        var = Variable("Param1", value)
        self.assertEqual(len(var.lookups), 2)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
            mock_lookup("fakeStack::FakeOutput2"): "resolved2",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, ["something", "resolved", "resolved2"])

    def test_variable_replace_lookups_dict(self):
        value = {
            "something": "${fakeStack::FakeOutput}",
            "other": "${fakeStack::FakeOutput2}",
        }
        var = Variable("Param1", value)
        self.assertEqual(len(var.lookups), 2)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
            mock_lookup("fakeStack::FakeOutput2"): "resolved2",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, {"something": "resolved", "other":
                                     "resolved2"})

    def test_variable_replace_lookups_mixed(self):
        value = {
            "something": [
                "${fakeStack::FakeOutput}",
                "other",
            ],
            "here": {
                "other": "${fakeStack::FakeOutput2}",
                "same": "${fakeStack::FakeOutput}",
                "mixed": "something:${fakeStack::FakeOutput3}",
            },
        }
        var = Variable("Param1", value)
        self.assertEqual(len(var.lookups), 3)
        resolved_lookups = {
            mock_lookup("fakeStack::FakeOutput"): "resolved",
            mock_lookup("fakeStack::FakeOutput2"): "resolved2",
            mock_lookup("fakeStack::FakeOutput3"): "resolved3",
        }
        var.replace(resolved_lookups)
        self.assertEqual(var.value, {
            "something": [
                "resolved",
                "other",
            ],
            "here": {
                "other": "resolved2",
                "same": "resolved",
                "mixed": "something:resolved3",
            },
        })

    def test_variable_resolve_nested_lookup(self):

        def mock_handler(value, context, provider, **kwargs):
            return "looked up: {}".format(value)

        register_lookup_handler("lookup", mock_handler)
        self.provider.get_output.return_value = "resolved"
        var = Variable(
            "Param1",
            "${lookup ${lookup ${output fakeStack::FakeOutput}}}",
        )
        self.assertEqual(
            len(var.lookups),
            1,
            "should only parse out the first complete lookup first",
        )
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "looked up: looked up: resolved")
