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

    def test_kms_lookup(self):
        lookups = extract_lookups("${kms CiADsGxJp1mCR21fjsVjVxr7RwuO2FE3ZJqC4iG0Lm+HkRKwAQEBAgB4A7BsSadZgkdtX47FY1ca+0cLjthRN2SaguIhtC5vh5EAAACHMIGEBgkqhkiG9w0BBwagdzB1AgEAMHAGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQM3IKyEoNEQVxN3BaaAgEQgEOpqa0rcl3WpHOmblAqL1rOPRyokO3YXcJAAB37h/WKLpZZRAWV2h9C67xjlsj3ebg+QIU91T/}")  # NOQA
        self.assertEqual(len(lookups), 1)
        lookup = list(lookups)[0]
        self.assertEqual(lookup.type, "kms")
        self.assertEqual(lookup.input, "CiADsGxJp1mCR21fjsVjVxr7RwuO2FE3ZJqC4iG0Lm+HkRKwAQEBAgB4A7BsSadZgkdtX47FY1ca+0cLjthRN2SaguIhtC5vh5EAAACHMIGEBgkqhkiG9w0BBwagdzB1AgEAMHAGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQM3IKyEoNEQVxN3BaaAgEQgEOpqa0rcl3WpHOmblAqL1rOPRyokO3YXcJAAB37h/WKLpZZRAWV2h9C67xjlsj3ebg+QIU91T/")  # NOQA

    def test_kms_lookup_with_region(self):
        lookups = extract_lookups("${kms us-west-2@CiADsGxJp1mCR21fjsVjVxr7RwuO2FE3ZJqC4iG0Lm+HkRKwAQEBAgB4A7BsSadZgkdtX47FY1ca+0cLjthRN2SaguIhtC5vh5EAAACHMIGEBgkqhkiG9w0BBwagdzB1AgEAMHAGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQM3IKyEoNEQVxN3BaaAgEQgEOpqa0rcl3WpHOmblAqL1rOPRyokO3YXcJAAB37h/WKLpZZRAWV2h9C67xjlsj3ebg+QIU91T/}")  # NOQA
        self.assertEqual(len(lookups), 1)
        lookup = list(lookups)[0]
        self.assertEqual(lookup.type, "kms")
        self.assertEqual(lookup.input, "us-west-2@CiADsGxJp1mCR21fjsVjVxr7RwuO2FE3ZJqC4iG0Lm+HkRKwAQEBAgB4A7BsSadZgkdtX47FY1ca+0cLjthRN2SaguIhtC5vh5EAAACHMIGEBgkqhkiG9w0BBwagdzB1AgEAMHAGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQM3IKyEoNEQVxN3BaaAgEQgEOpqa0rcl3WpHOmblAqL1rOPRyokO3YXcJAAB37h/WKLpZZRAWV2h9C67xjlsj3ebg+QIU91T/")  # NOQA

    def test_kms_file_lookup(self):
        lookups = extract_lookups("${kms file://path/to/some/file.txt}")
        self.assertEqual(len(lookups), 1)
        lookup = list(lookups)[0]
        self.assertEqual(lookup.type, "kms")
        self.assertEqual(lookup.input, "file://path/to/some/file.txt")
