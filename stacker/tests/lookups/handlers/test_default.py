from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.lookups.handlers.default import DefaultLookup

from ...factories import mock_context, mock_provider


class TestDefaultLookup(unittest.TestCase):
    def setUp(self):
        self.provider = mock_provider()
        self.context = mock_context(
            namespace='test', environment={'env_var': 'val_in_env'})

    def test_env_var_present(self):
        lookup_val = "env_var::fallback"
        value = DefaultLookup.handle(lookup_val,
                                     provider=self.provider,
                                     context=self.context)
        assert value == 'val_in_env'

    def test_env_var_missing(self):
        lookup_val = "bad_env_var::fallback"
        value = DefaultLookup.handle(lookup_val,
                                     provider=self.provider,
                                     context=self.context)
        assert value == 'fallback'

    def test_invalid_value(self):
        value = "env_var:fallback"
        with self.assertRaises(ValueError):
            DefaultLookup.handle(value)
