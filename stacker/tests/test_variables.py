from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from troposphere import s3

from stacker.blueprints.variables.types import TroposphereType
from stacker.lookups.handlers import LookupHandler
from stacker.variables import Variable
from stacker.lookups import register_lookup_handler

from .factories import mock_context, mock_provider


class MockLookup(LookupHandler):
    @classmethod
    def handle(cls, value, context, provider):
        return str(value)


class TestVariables(unittest.TestCase):

    def setUp(self):
        self.provider = mock_provider()
        self.context = mock_context()

        register_lookup_handler("test", MockLookup)

    def test_variable_replace_no_lookups(self):
        var = Variable("Param1", "2")
        self.assertEqual(var.value, "2")

    def test_variable_resolve_simple_lookup(self):
        var = Variable("Param1", "${noop test}")
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "test")

    def test_variable_replace_multiple_lookups_string(self):
        var = Variable(
            "Param1",
            "url://"  # 0
            "${test resolved}"  # 1
            "@"  # 2
            "${test resolved2}",  # 3
        )
        var.resolve(self.context, self.provider)
        self.assertEqual(var.value, "url://resolved@resolved2")

    def test_variable_replace_no_lookups_list(self):
        var = Variable("Param1", ["something", "here"])
        self.assertEqual(var.value, ["something", "here"])

    def test_variable_replace_lookups_list(self):
        value = ["something", "${test resolved}", "${test resolved2}"]
        var = Variable("Param1", value)
        var.resolve(self.context, self.provider)
        self.assertEqual(var.value, ["something", "resolved", "resolved2"])

    def test_variable_replace_lookups_dict(self):
        value = {
            "something": "${test resolved}",
            "other": "${test resolved2}",
        }
        var = Variable("Param1", value)
        var.resolve(self.context, self.provider)
        self.assertEqual(var.value, {"something": "resolved",
                                     "other": "resolved2"})

    def test_variable_replace_lookups_mixed(self):
        value = {
            "list": [
                "${test 1}",
                "2",
            ],
            "dict": {
                "1": "${test a}",
                "2": "${test b}",
                "3": "c:${test d}",
            },
        }
        var = Variable("Param1", value)
        var.resolve(self.context, self.provider)
        self.assertEqual(var.value, {
            "list": ["1", "2"],
            "dict": {
                "1": "a",
                "2": "b",
                "3": "c:d",
            },
        })

    def test_variable_resolve_nested_lookup(self):
        var = Variable(
            "Param1",
            "${test a:${test b:${test c}}}",
        )
        var.resolve(self.context, self.provider)
        self.assertTrue(var.resolved)
        self.assertEqual(var.value, "a:b:c")

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
