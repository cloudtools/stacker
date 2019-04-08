from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.lookups.handlers.rxref import RxrefLookup

from ...factories import mock_context, mock_provider


class TestRxrefHandler(unittest.TestCase):

    def setUp(self):
        self.context = mock_context()
        self.stack_name = "stack-name"
        self.stack_fqn = self.context.get_fqn(self.stack_name)
        self.provider = mock_provider(
            outputs={self.stack_fqn: {"SomeOutput": "Test Output"}})

    def test_rxref_handler(self):
        value = RxrefLookup.handle("{}::SomeOutput".format(self.stack_name),
                                   provider=self.provider,
                                   context=self.context)
        self.assertEqual(value, "Test Output")
