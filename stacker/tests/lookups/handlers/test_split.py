from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.lookups.handlers.split import handler


class TestSplitLookup(unittest.TestCase):
    def test_single_character_split(self):
        value = ",::a,b,c"
        expected = ["a", "b", "c"]
        assert handler(value) == expected

    def test_multi_character_split(self):
        value = ",,::a,,b,c"
        expected = ["a", "b,c"]
        assert handler(value) == expected

    def test_invalid_value_split(self):
        value = ",:a,b,c"
        with self.assertRaises(ValueError):
            handler(value)
