import unittest

from stacker.environment import parse_environment

test_env = """key1: value1
# some: comment
 # here: about
# key2
key2: value2
# another comment here
key3: some:complex::value
# one more here as well
key4: :otherValue:
key5: <another>@value
"""


class TestEnvironment(unittest.TestCase):

    def test_simple_key_value_parsing(self):
        parsed_env = parse_environment(test_env)
        self.assertTrue(isinstance(parsed_env, dict))
        self.assertEqual(parsed_env['key1'], 'value1')
        self.assertEqual(parsed_env['key2'], 'value2')
        self.assertEqual(parsed_env['key3'], 'some:complex::value')
        self.assertEqual(parsed_env['key4'], ':otherValue:')
        self.assertEqual(parsed_env['key5'], '<another>@value')
        self.assertEqual(len(parsed_env.keys()), 5)
