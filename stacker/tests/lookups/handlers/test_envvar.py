from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
from stacker.lookups.handlers.envvar import EnvvarLookup
import os


class TestEnvVarHandler(unittest.TestCase):

    def setUp(self):
        self.testkey = 'STACKER_ENVVAR_TESTCASE'
        self.invalidtestkey = 'STACKER_INVALID_ENVVAR_TESTCASE'
        self.testval = 'TestVal'
        os.environ[self.testkey] = self.testval

    def test_valid_envvar(self):
        value = EnvvarLookup.handle(self.testkey)
        self.assertEqual(value, self.testval)

    def test_invalid_envvar(self):
        with self.assertRaises(ValueError):
            EnvvarLookup.handle(self.invalidtestkey)
