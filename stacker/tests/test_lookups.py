from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.lookups import extract_lookups, extract_lookups_from_string


class TestLookupExtraction(unittest.TestCase):

    def test_no_lookups(self):
        lookups = extract_lookups("value")
        self.assertEqual(lookups, set())

    def test_single_lookup_string(self):
        lookups = extract_lookups("${output fakeStack::FakeOutput}")
        self.assertEqual(len(lookups), 1)

    def test_multiple_lookups_string(self):
        lookups = extract_lookups(
            "url://${output fakeStack::FakeOutput}@"
            "${output fakeStack::FakeOutput2}"
        )
        self.assertEqual(len(lookups), 2)
        self.assertEqual(list(lookups)[0].type, "output")

    def test_lookups_list(self):
        lookups = extract_lookups([
            "something",
            "${output fakeStack::FakeOutput}"
        ])
        self.assertEqual(len(lookups), 1)

    def test_lookups_dict(self):
        lookups = extract_lookups({
            "something": "${output fakeStack::FakeOutput}",
            "other": "value",
        })
        self.assertEqual(len(lookups), 1)

    def test_lookups_mixed(self):
        lookups = extract_lookups({
            "something": "${output fakeStack::FakeOutput}",
            "list": ["value", "${output fakeStack::FakeOutput2}"],
            "dict": {
                "other": "value",
                "another": "${output fakeStack::FakeOutput3}",
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

    def test_kms_lookup_with_equals(self):
        lookups = extract_lookups("${kms us-east-1@AQECAHjLp186mZ+mgXTQSytth/ibiIdwBm8CZAzZNSaSkSRqswAAAG4wbAYJKoZIhvcNAQcGoF8wXQIBADBYBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDLNmhGU6fe4vp175MAIBEIAr+8tUpi7SDzOZm+FFyYvWXhs4hEEyaazIn2dP8a+yHzZYDSVYGRpfUz34bQ==}")  # NOQA
        self.assertEqual(len(lookups), 1)
        lookup = list(lookups)[0]
        self.assertEqual(lookup.type, "kms")
        self.assertEqual(lookup.input, "us-east-1@AQECAHjLp186mZ+mgXTQSytth/ibiIdwBm8CZAzZNSaSkSRqswAAAG4wbAYJKoZIhvcNAQcGoF8wXQIBADBYBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDLNmhGU6fe4vp175MAIBEIAr+8tUpi7SDzOZm+FFyYvWXhs4hEEyaazIn2dP8a+yHzZYDSVYGRpfUz34bQ==")  # NOQA

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

    def test_valid_extract_lookups_from_string(self):
        _type = "output"
        _input = "vpc::PublicSubnets"
        value = "${%s %s}" % (_type, _input)
        lookups = extract_lookups_from_string(value)
        lookup = lookups.pop()
        assert lookup.type == _type
        assert lookup.input == _input
        assert lookup.raw == "%s %s" % (_type, _input)
