import unittest

from stacker.lookups import extract_lookups


class TestLookupExtraction(unittest.TestCase):

    def test_no_lookups(self):
        lookups = extract_lookups("value")
        self.assertEqual(lookups, set())

    def test_single_lookup_string(self):
        lookups = extract_lookups("${output fakeStack::FakeOutput}")
        self.assertEqual(len(lookups), 1)

    def test_multiple_lookups_string(self):
        lookups = extract_lookups(
            "url://${fakeStack::FakeOutput}@${fakeStack::FakeOutput2}"
        )
        self.assertEqual(len(lookups), 2)
        self.assertEqual(list(lookups)[0].type, "output")

    def test_lookups_list(self):
        lookups = extract_lookups(["something", "${fakeStack::FakeOutput}"])
        self.assertEqual(len(lookups), 1)

    def test_lookups_dict(self):
        lookups = extract_lookups({
            "something": "${fakeStack::FakeOutput}",
            "other": "value",
        })
        self.assertEqual(len(lookups), 1)

    def test_lookups_mixed(self):
        lookups = extract_lookups({
            "something": "${fakeStack::FakeOutput}",
            "list": ["value", "${fakeStack::FakeOutput2}"],
            "dict": {
                "other": "value",
                "another": "${fakeStack::FakeOutput3}",
            },
        })
        self.assertEqual(len(lookups), 3)

    def test_nested_lookups_string(self):
        lookups = extract_lookups(
            "${noop ${output stack::Output},${output stack::Output2}}"
        )
        self.assertEqual(len(lookups), 2)

    def test_comma_delimited(self):
        lookups = extract_lookups("${noop val1,val2}")
        self.assertEqual(len(lookups), 1)
