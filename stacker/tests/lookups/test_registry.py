import unittest

from mock import patch

from stacker.exceptions import (
    UnknownLookupType,
    FailedVariableLookup,
)

from stacker.lookups.registry import (
    LOOKUP_HANDLERS,
    resolve_lookups,
)

from stacker.variables import Variable

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
        variable = Variable("MyVar", "${bad_lookup foo}")

        with self.assertRaises(UnknownLookupType):
            resolve_lookups(variable, self.ctx, self.provider)

    def test_resolve_lookups_list_unknown_lookup(self):
        variable = Variable(
            "MyVar", [
                "${bad_lookup foo}", "${output foo::bar}", "random string",
            ]
        )

        with self.assertRaises(UnknownLookupType):
            resolve_lookups(variable, self.ctx, self.provider)

    @patch("stacker.lookups.handlers.output")
    def test_resolve_lookups_string_failed_variable_lookup(self, mock_handler):
        mock_handler.side_effect = ValueError("FakeError")

        variable = Variable("MyVar", "${output foo::bar}")

        with self.assertRaises(FailedVariableLookup):
            resolve_lookups(variable, self.ctx, self.provider)

    @patch("stacker.lookups.handlers.output")
    def test_resolve_lookups_list_failed_variable_lookup(self, mock_handler):
        mock_handler.side_effect = ValueError("FakeError")

        variable = Variable(
            "MyVar", [
                "random string", "${output foo::bar}", "random string",
            ]
        )

        with self.assertRaises(FailedVariableLookup):
            resolve_lookups(variable, self.ctx, self.provider)
