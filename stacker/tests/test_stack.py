from mock import MagicMock
import unittest

from stacker.context import Context
from stacker.stack import _gather_variables, Stack
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
            variables={
                "Var1": "${noop fakeStack3::FakeOutput}",
                "Var2": (
                    "some.template.value:${output fakeStack2::FakeOutput}:"
                    "${output fakeStack::FakeOutput}"
                ),
                "Var3": "${output fakeStack::FakeOutput},"
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
                "Var1": "${output vpc.1::FakeOutput}",
            },
        )
        stack = Stack(definition=definition, context=self.context)
        with self.assertRaises(ValueError):
            stack.requires

    def test_stack_cfn_parameters(self):
        definition = generate_definition(
            base_name="vpc",
            stack_id=1,
            variables={
                "Param1": "${output fakeStack::FakeOutput}",
            },
        )
        stack = Stack(definition=definition, context=self.context)
        stack._blueprint = MagicMock()
        stack._blueprint.get_parameter_values.return_value = {
            "Param2": "Some Resolved Value",
        }
        self.assertEqual(len(stack.parameter_values.keys()), 1)
        param = stack.parameter_values["Param2"]
        self.assertEqual(param, "Some Resolved Value")

    def test_gather_variables_fails_on_parameters_in_stack_def(self):
        sdef = self.sd
        sdef["parameters"] = {"Address": "10.0.0.1", "Foo": "BAR"}
        with self.assertRaises(AttributeError):
            _gather_variables(sdef)
