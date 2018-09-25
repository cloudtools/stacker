from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from mock import MagicMock

from troposphere import s3
from stacker.blueprints.variables.types import TroposphereType
from stacker.variables import Variable
from stacker.lookups import register_lookup_handler
from stacker.stack import Stack


from .factories import generate_definition


class TestVariables(unittest.TestCase):

    def setUp(self):
        self.provider = MagicMock()
        self.context = MagicMock()

    def test_variable_replace_no_lookups(self):
        var = Variable("Param1", "2")
        self.assertEqual(var.value, "2")

    def test_variable_replace_simple_lookup(self):
        var = Variable("Param1", "${output fakeStack::FakeOutput}")
        var._value._resolve("resolved")
        self.assertEqual(var.value, "resolved")

    def test_variable_resolve_simple_lookup(self):
        stack = Stack(
            definition=generate_definition("vpc", 1),
            context=self.context)
        stack.set_outputs({
            "FakeOutput": "resolved",
            "FakeOutput2": "resolved2",
        })

        self.context.get_stack.return_value = stack

        var = Variable("Param1", "${output fakeStack::FakeOutput}")
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "resolved")

    def test_variable_resolve_default_lookup_empty(self):
        var = Variable("Param1", "${default fakeStack::}")
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "")

    def test_variable_replace_multiple_lookups_string(self):
        var = Variable(
            "Param1",
            "url://"  # 0
            "${output fakeStack::FakeOutput}"  # 1
            "@"  # 2
            "${output fakeStack::FakeOutput2}",  # 3
        )
        var._value[1]._resolve("resolved")
        var._value[3]._resolve("resolved2")
        self.assertEqual(var.value, "url://resolved@resolved2")

    def test_variable_resolve_multiple_lookups_string(self):
        var = Variable(
            "Param1",
            "url://${output fakeStack::FakeOutput}@"
            "${output fakeStack::FakeOutput2}",
        )

        stack = Stack(
            definition=generate_definition("vpc", 1),
            context=self.context)
        stack.set_outputs({
            "FakeOutput": "resolved",
            "FakeOutput2": "resolved2",
        })

        self.context.get_stack.return_value = stack
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "url://resolved@resolved2")

    def test_variable_replace_no_lookups_list(self):
        var = Variable("Param1", ["something", "here"])
        self.assertEqual(var.value, ["something", "here"])

    def test_variable_replace_lookups_list(self):
        value = ["something",  # 0
                 "${output fakeStack::FakeOutput}",  # 1
                 "${output fakeStack::FakeOutput2}"  # 2
                 ]
        var = Variable("Param1", value)

        var._value[1]._resolve("resolved")
        var._value[2]._resolve("resolved2")
        self.assertEqual(var.value, ["something", "resolved", "resolved2"])

    def test_variable_replace_lookups_dict(self):
        value = {
            "something": "${output fakeStack::FakeOutput}",
            "other": "${output fakeStack::FakeOutput2}",
        }
        var = Variable("Param1", value)
        var._value["something"]._resolve("resolved")
        var._value["other"]._resolve("resolved2")
        self.assertEqual(var.value, {"something": "resolved", "other":
                                     "resolved2"})

    def test_variable_replace_lookups_mixed(self):
        value = {
            "something": [
                "${output fakeStack::FakeOutput}",
                "other",
            ],
            "here": {
                "other": "${output fakeStack::FakeOutput2}",
                "same": "${output fakeStack::FakeOutput}",
                "mixed": "something:${output fakeStack::FakeOutput3}",
            },
        }
        var = Variable("Param1", value)
        var._value["something"][0]._resolve("resolved")
        var._value["here"]["other"]._resolve("resolved2")
        var._value["here"]["same"]._resolve("resolved")
        var._value["here"]["mixed"][1]._resolve("resolved3")
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
        stack = Stack(
            definition=generate_definition("vpc", 1),
            context=self.context)
        stack.set_outputs({
            "FakeOutput": "resolved",
            "FakeOutput2": "resolved2",
        })

        def mock_handler(value, context, provider, **kwargs):
            return "looked up: {}".format(value)

        register_lookup_handler("lookup", mock_handler)
        self.context.get_stack.return_value = stack
        var = Variable(
            "Param1",
            "${lookup ${lookup ${output fakeStack::FakeOutput}}}",
        )
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "looked up: looked up: resolved")

    def test_troposphere_type_no_from_dict(self):
        with self.assertRaises(ValueError):
            TroposphereType(object)

        with self.assertRaises(ValueError):
            TroposphereType(object, many=True)

    def test_troposphere_type_create(self):
        troposphere_type = TroposphereType(s3.Bucket)
        created = troposphere_type.create(
            {"MyBucket": {"BucketName": "test-bucket"}})
        self.assertTrue(isinstance(created, s3.Bucket))
        self.assertTrue(created.properties["BucketName"], "test-bucket")

    def test_troposphere_type_create_multiple(self):
        troposphere_type = TroposphereType(s3.Bucket, many=True)
        created = troposphere_type.create({
            "FirstBucket": {"BucketName": "test-bucket"},
            "SecondBucket": {"BucketName": "other-test-bucket"},
        })
        self.assertTrue(isinstance(created, list))
