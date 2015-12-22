import unittest

from mock import patch
from stacker.config import parse_config
from stacker.environment import parse_environment
from stacker import exceptions

config = """a: $a
b: $b
c: $c"""


class TestConfig(unittest.TestCase):
    def test_missing_env(self):
        env = {'a': 'A'}
        with self.assertRaises(exceptions.MissingEnvironment) as expected:
            parse_config(config, env)
        self.assertEqual(expected.exception.key, 'b')

    def test_no_variable_config(self):
        c = parse_config("a: A", {})
        self.assertEqual(c["a"], "A")

    def test_valid_env_substitution(self):
        c = parse_config("a: $a", {"a": "A"})
        self.assertEqual(c["a"], "A")

    @patch('stacker.config.translators.vault.get_vaulted_value')
    def test_custom_constructors(self, patched):
        patched.return_value = 'stub'
        c = parse_config("a: $a", {"a": "!vault some_encrypted_value"})
        self.assertEqual(c['a'], 'stub')

    @patch('stacker.config.translators.vault.subprocess')
    def test_vault_constructor(self, patched):
        patched.check_output.return_value = 'secret\n'
        c = parse_config('a: $a', {'a': '!vault secret/hello@value'})
        self.assertEqual(c['a'], 'secret')

    def test_blank_env_values(self):
        conf = """a: ${key1}"""
        e = parse_environment("""key1:""")
        c = parse_config(conf, e)
        self.assertEqual(c['a'], None)
        e = parse_environment("""key1: !!str""")
        c = parse_config(conf, e)
        self.assertEqual(c['a'], "")
