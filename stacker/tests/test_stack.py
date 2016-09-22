from mock import MagicMock
import unittest

from stacker.context import Context
from stacker.stack import _gather_parameters, Stack
from .factories import generate_definition


class TestStack(unittest.TestCase):

    def setUp(self):
        self.sd = {"name": "test"}
        self.context = Context({"namespace": "namespace"})
        self.stack = Stack(
            definition=generate_definition("vpc", 1),
            context=self.context,
        )

    def test_stack_requires(self):
        definition = generate_definition(
            base_name="vpc",
            stack_id=1,
            parameters={
                "ExternalParameter": "fakeStack2::FakeParameter",
            },
            variables={
                "Var1": "${noop fakeStack3::FakeOutput}",
                "Var2": (
                    "some.template.value:${fakeStack2::FakeOutput}:"
                    "${fakeStack::FakeOutput}"
                ),
                "Var3": "${fakeStack::FakeOutput},"
                        "${output fakeStack2::FakeOutput}",
            },
            requires=[self.context.get_fqn("fakeStack")],
        )
        stack = Stack(definition=definition, context=self.context)
        self.assertEqual(len(stack.requires), 2)
        self.assertIn(
            self.context.get_fqn("fakeStack"),
            stack.requires,
        )
        self.assertIn(
            self.context.get_fqn("fakeStack2"),
            stack.requires,
        )

    def test_stack_requires_circular_ref(self):
        definition = generate_definition(
            base_name="vpc",
            stack_id=1,
            variables={
                "Var1": "${vpc.1::FakeOutput}",
            },
        )
        stack = Stack(definition=definition, context=self.context)
        with self.assertRaises(ValueError):
            stack.requires

    def test_stack_cfn_parameters(self):
        definition = generate_definition(
            base_name="vpc",
            stack_id=1,
            parameters={
                "Param1": "fakeStack::FakeOutput",
            },
        )
        stack = Stack(definition=definition, context=self.context)
        stack._blueprint = MagicMock()
        stack._blueprint.get_cfn_parameters.return_value = {
            "Param2": "Some Resolved Value",
        }
        self.assertEqual(len(stack.cfn_parameters.keys()), 2)
        param = stack.cfn_parameters["Param2"]
        self.assertEqual(param, "Some Resolved Value")

    def test_empty_parameters(self):
        build_action_parameters = {}
        self.assertEqual({}, _gather_parameters(self.sd,
                                                build_action_parameters))

    def test_generic_build_action_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        build_action_parameters = {"Address": "192.168.1.1"}
        result = _gather_parameters(sdef, build_action_parameters)
        self.assertEqual(result["Address"], "192.168.1.1")
        self.assertEqual(result["Foo"], "BAR")

    def test_stack_specific_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        build_action_parameters = {"test::Address": "192.168.1.1"}
        result = _gather_parameters(sdef, build_action_parameters)
        self.assertEqual(result["Address"], "192.168.1.1")
        self.assertEqual(result["Foo"], "BAR")

    def test_invalid_stack_specific_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        build_action_parameters = {"FAKE::Address": "192.168.1.1"}
        result = _gather_parameters(sdef, build_action_parameters)
        self.assertEqual(result["Address"], "10.0.0.1")
        self.assertEqual(result["Foo"], "BAR")

    def test_specific_vs_generic_build_action_override(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        build_action_parameters = {
            "test::Address": "192.168.1.1",
            "Address": "10.0.0.1"}
        result = _gather_parameters(sdef, build_action_parameters)
        self.assertEqual(result["Address"], "192.168.1.1")
        self.assertEqual(result["Foo"], "BAR")
