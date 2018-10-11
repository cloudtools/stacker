from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from mock import MagicMock

from stacker.exceptions import (
    UnknownLookupType,
    FailedVariableLookup,
)

from stacker.lookups.registry import LOOKUP_HANDLERS

from stacker.variables import Variable, VariableValueLookup

from ..factories import (
    mock_context,
    mock_provider,
)


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.ctx = mock_context()
        self.provider = mock_provider()

    def test_autoloaded_lookup_handlers(self):
        handlers = [
            "output", "xref", "kms", "ssmstore", "envvar", "rxref", "ami",
            "file", "split", "default", "hook_data", "dynamodb",
        ]
        for handler in handlers:
            try:
                LOOKUP_HANDLERS[handler]
            except KeyError:
                self.assertTrue(
                    False,
                    "Lookup handler: '{}' was not registered".format(handler),
                )

    def test_resolve_lookups_string_unknown_lookup(self):
        with self.assertRaises(UnknownLookupType):
            Variable("MyVar", "${bad_lookup foo}")

    def test_resolve_lookups_list_unknown_lookup(self):
        with self.assertRaises(UnknownLookupType):
            Variable(
                "MyVar", [
                    "${bad_lookup foo}", "random string",
                ]
            )

    def resolve_lookups_with_output_handler_raise_valueerror(self, variable):
        """Mock output handler to throw ValueError, then run resolve_lookups
        on the given variable.
        """
        mock_handler = MagicMock(side_effect=ValueError("Error"))

        # find the only lookup in the variable
        for value in variable._value:
            if isinstance(value, VariableValueLookup):
                value.handler = mock_handler

        with self.assertRaises(FailedVariableLookup) as cm:
            variable.resolve(self.ctx, self.provider)

        self.assertIsInstance(cm.exception.error, ValueError)

    def test_resolve_lookups_string_failed_variable_lookup(self):
        variable = Variable("MyVar", "${output foo::bar}")
        self.resolve_lookups_with_output_handler_raise_valueerror(variable)

    def test_resolve_lookups_list_failed_variable_lookup(self):
        variable = Variable(
            "MyVar", [
                "random string", "${output foo::bar}", "random string",
            ]
        )
        self.resolve_lookups_with_output_handler_raise_valueerror(variable)
