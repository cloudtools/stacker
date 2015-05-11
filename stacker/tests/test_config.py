import unittest

from stacker.config import parse_config, MissingEnvironment

config = """a: $a
b: $b
c: $c"""


class TestConfig(unittest.TestCase):
    def test_missing_env(self):
        env = {'a': 'A'}
        try:
            parse_config(config, env)
        except MissingEnvironment as e:
            self.assertEqual(e.key, 'b')

    def test_no_variable_config(self):
        c = parse_config("a: A", {})
        self.assertEqual(c["a"], "A")

    def valid_env_substitution(self):
        c = parse_config("a: $a", {"a": "A"})
        self.assertEqual(c["a"], "A")
