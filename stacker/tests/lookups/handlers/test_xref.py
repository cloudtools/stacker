from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from mock import MagicMock
import unittest

from stacker.lookups.handlers.xref import handler


class TestXrefHandler(unittest.TestCase):

    def setUp(self):
        self.provider = MagicMock()
        self.context = MagicMock()

    def test_xref_handler(self):
        self.provider.get_output.return_value = "Test Output"
        value = handler("fully-qualified-stack-name::SomeOutput",
                        provider=self.provider, context=self.context)
        self.assertEqual(value, "Test Output")
        self.assertEqual(self.context.get_fqn.call_count, 0)
        args = self.provider.get_output.call_args
        self.assertEqual(args[0][0], "fully-qualified-stack-name")
        self.assertEqual(args[0][1], "SomeOutput")
