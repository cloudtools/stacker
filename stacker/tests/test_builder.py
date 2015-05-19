import unittest
from collections import namedtuple

from stacker.builder import (
    gather_parameters, handle_missing_parameters, MissingParameterException
)


class TestGatherParameters(unittest.TestCase):
    def setUp(self):
        self.sd = {"name": "test"}

    def test_empty_parameters(self):
        builder_parameters = {}
        self.assertEqual({}, gather_parameters(self.sd, builder_parameters))

    def test_generic_builder_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        builder_parameters = {"Address": "192.168.1.1"}
        result = gather_parameters(sdef, builder_parameters)
        self.assertEqual(result["Address"], "192.168.1.1")
        self.assertEqual(result["Foo"], "BAR")

    def test_stack_specific_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        builder_parameters = {"test::Address": "192.168.1.1"}
        result = gather_parameters(sdef, builder_parameters)
        self.assertEqual(result["Address"], "192.168.1.1")
        self.assertEqual(result["Foo"], "BAR")

    def test_invalid_stack_specific_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        builder_parameters = {"FAKE::Address": "192.168.1.1"}
        result = gather_parameters(sdef, builder_parameters)
        self.assertEqual(result["Address"], "10.0.0.1")
        self.assertEqual(result["Foo"], "BAR")

    def test_specific_vs_generic_builder_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        builder_parameters = {
            "test::Address": "192.168.1.1",
            "Address": "10.0.0.1"}
        result = gather_parameters(sdef, builder_parameters)
        self.assertEqual(result["Address"], "192.168.1.1")
        self.assertEqual(result["Foo"], "BAR")


Parameter = namedtuple('Parameter', ['key', 'value'])


class MockStack(object):
    def __init__(self, parameters):
        self.parameters = []
        for k, v in parameters.items():
            self.parameters.append(Parameter(key=k, value=v))


class TestHandleMissingParameters(unittest.TestCase):
    def test_gather_missing_from_stack(self):
        stack_params = {'Address': '10.0.0.1'}
        stack = MockStack(stack_params)
        def_params = {}
        required = ['Address']
        self.assertEqual(
            handle_missing_parameters(def_params, required, stack),
            stack_params.items())

    def test_missing_params_no_stack(self):
        params = {}
        required = ['Address']
        with self.assertRaises(MissingParameterException) as cm:
            handle_missing_parameters(params, required)

        self.assertEqual(cm.exception.parameters, required)

    def test_stack_params_dont_override_given_params(self):
        stack_params = {'Address': '10.0.0.1'}
        stack = MockStack(stack_params)
        def_params = {'Address': '192.168.0.1'}
        required = ['Address']
        result = handle_missing_parameters(def_params, required, stack)
        self.assertEqual(result, def_params.items())
