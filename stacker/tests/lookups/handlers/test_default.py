from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from mock import MagicMock
import unittest

from stacker.context import Context
from stacker.lookups.handlers.default import handler


class TestDefaultLookup(unittest.TestCase):

    def setUp(self):
        self.provider = MagicMock()
        self.context = Context(
            environment={
                'namespace': 'test',
                'env_var': 'val_in_env'}
        )

    def test_env_var_present(self):
        lookup_val = "env_var::fallback"
        value = handler(lookup_val,
                        provider=self.provider,
                        context=self.context)
        assert value == 'val_in_env'

    def test_env_var_missing(self):
        lookup_val = "bad_env_var::fallback"
        value = handler(lookup_val,
                        provider=self.provider,
                        context=self.context)
        assert value == 'fallback'

    def test_invalid_value(self):
        value = "env_var:fallback"
        with self.assertRaises(ValueError):
            handler(value)
