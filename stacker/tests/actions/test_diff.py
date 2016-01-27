import unittest

from stacker.actions.diff import diff_dictionaries


class TestDiffDictionary(unittest.TestCase):
    def setUp(self):
        self.old_dict = {
            'a': 'Apple',
            'b': 'Banana',
            'c': 'Corn',
        }
        self.new_dict = {
            'a': 'Apple',
            'b': 'Bob',
            'd': 'Doug',
        }

    def test_diff_dictionaries(self):
        [count, changes] = diff_dictionaries(self.old_dict, self.new_dict)
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
