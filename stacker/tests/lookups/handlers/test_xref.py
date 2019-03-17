from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.lookups.handlers.xref import XrefLookup

from ...factories import mock_context, mock_provider


class TestXrefHandler(unittest.TestCase):

    def setUp(self):
        self.stack_fqn = "fully-qualified-stack-name"
        self.context = mock_context()
        self.provider = mock_provider(
            outputs={self.stack_fqn: {"SomeOutput": "Test Output"}})

    def test_xref_handler(self):
        value = XrefLookup.handle("{}::SomeOutput".format(self.stack_fqn),
                                  provider=self.provider,
                                  context=self.context)
        self.assertEqual(value, "Test Output")
