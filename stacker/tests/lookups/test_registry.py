from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.lookups.registry import LOOKUP_HANDLERS


class TestRegistry(unittest.TestCase):

    def test_autoloaded_lookup_handlers(self):
        handlers = ["output", "xref"]
        for handler in handlers:
            try:
                LOOKUP_HANDLERS[handler]
            except KeyError:
                self.assertTrue(
                    False,
                    "Lookup handler: '{}' was not registered".format(handler),
                )
