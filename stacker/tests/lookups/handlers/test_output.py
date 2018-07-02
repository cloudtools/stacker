from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from mock import MagicMock
import unittest

from stacker.stack import Stack
from ...factories import generate_definition
from stacker.lookups.handlers.output import handler


class TestOutputHandler(unittest.TestCase):

    def setUp(self):
        self.context = MagicMock()

    def test_output_handler(self):
        stack = Stack(
            definition=generate_definition("vpc", 1),
            context=self.context)
        stack.set_outputs({
            "SomeOutput": "Test Output"})
        self.context.get_stack.return_value = stack
        value = handler("stack-name::SomeOutput", context=self.context)
        self.assertEqual(value, "Test Output")
        self.assertEqual(self.context.get_stack.call_count, 1)
        args = self.context.get_stack.call_args
        self.assertEqual(args[0][0], "stack-name")
