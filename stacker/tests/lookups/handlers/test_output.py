from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from mock import MagicMock
import unittest

from stacker.stack import Stack
from stacker.lookups.handlers.output import OutputLookup

from ...factories import generate_definition, mock_context, mock_provider


class TestOutputHandler(unittest.TestCase):
    def setUp(self):
        stack_def = generate_definition("vpc", 1)
        self.context = mock_context()
        self.stack = Stack(definition=stack_def, context=self.context)
        self.context.get_stacks = MagicMock(return_value=[self.stack])
        self.provider = mock_provider(
            outputs={self.stack.fqn: {"SomeOutput": "Test Output"}})

    def test_output_handler(self):
        value = OutputLookup.handle("{}::SomeOutput".format(self.stack.name),
                                    context=self.context,
                                    provider=self.provider)
        self.assertEqual(value, "Test Output")
