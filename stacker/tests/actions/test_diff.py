import unittest

from stacker.actions.diff import (
    diff_dictionaries,
    diff_parameters
)


class TestDiffDictionary(unittest.TestCase):
    def test_diff_dictionaries(self):
        old_dict = {
            "a": "Apple",
            "b": "Banana",
            "c": "Corn",
        }
        new_dict = {
            "a": "Apple",
            "b": "Bob",
            "d": "Doug",
        }

        [count, changes] = diff_dictionaries(old_dict, new_dict)
        self.assertEqual(count, 3)
        expected_output = [
            [" ", "a", "Apple"],
            ["-", "b", "Banana"],
            ["+", "b", "Bob"],
            ["-", "c", "Corn"],
            ["+", "d", "Doug"],
        ]
        changes.sort()
        expected_output.sort()

        # compare all the outputs to the expected change
        for expected_change in expected_output:
            change = changes.pop(0)
            self.assertListEqual(change, expected_change)

        # No extra output
        self.assertEqual(len(changes), 0)


class TestDiffParameters(unittest.TestCase):
    def test_diff_parameters_no_changes(self):
        old_params = {
            "a": "Apple"
        }
        new_params = {
            "a": "Apple"
        }

        param_diffs = diff_parameters(old_params, new_params)
        self.assertEquals(param_diffs, [])
