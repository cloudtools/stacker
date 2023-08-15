import unittest

from operator import attrgetter
from stacker.actions.diff import (
    diff_dictionaries,
    diff_parameters,
    DictValue
)


class TestDictValueFormat(unittest.TestCase):
    def test_status(self):
        added = DictValue("k0", None, "value_0")
        self.assertEqual(added.status(), DictValue.ADDED)
        removed = DictValue("k1", "value_1", None)
        self.assertEqual(removed.status(), DictValue.REMOVED)
        modified = DictValue("k2", "value_1", "value_2")
        self.assertEqual(modified.status(), DictValue.MODIFIED)
        unmodified = DictValue("k3", "value_1", "value_1")
        self.assertEqual(unmodified.status(), DictValue.UNMODIFIED)

    def test_format(self):
        added = DictValue("k0", None, "value_0")
        self.assertEqual(added.changes(),
                         ['+%s = %s' % (added.key, added.new_value)])
        removed = DictValue("k1", "value_1", None)
        self.assertEqual(removed.changes(),
                         ['-%s = %s' % (removed.key, removed.old_value)])
        modified = DictValue("k2", "value_1", "value_2")
        self.assertEqual(modified.changes(), [
            '-%s = %s' % (modified.key, modified.old_value),
            '+%s = %s' % (modified.key, modified.new_value)
        ])
        unmodified = DictValue("k3", "value_1", "value_1")
        self.assertEqual(unmodified.changes(), [' %s = %s' % (
            unmodified.key, unmodified.old_value)])
        self.assertEqual(unmodified.changes(), [' %s = %s' % (
            unmodified.key, unmodified.new_value)])


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
            DictValue("a", "Apple", "Apple"),
            DictValue("b", "Banana", "Bob"),
            DictValue("c", "Corn", None),
            DictValue("d", None, "Doug"),
        ]
        expected_output.sort(key=attrgetter("key"))

        # compare all the outputs to the expected change
        for expected_change in expected_output:
            change = changes.pop(0)
            self.assertEqual(change, expected_change)

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
