import unittest

import string
import os

from stacker.util import (
    get_bucket_location, cf_safe_name, load_object_from_string,
    camel_to_snake)

regions = ['us-east-1', 'cn-north-1', 'ap-northeast-1', 'eu-west-1',
           'ap-southeast-1', 'ap-southeast-2', 'us-west-2', 'us-gov-west-1',
           'us-west-1', 'eu-central-1', 'sa-east-1']


class TestUtil(unittest.TestCase):
    def test_get_bucket_location(self):
        for r in regions:
            expected = r
            if r == "us-east-1":
                expected = ""
            self.assertEqual(get_bucket_location(r), expected)

    def test_cf_safe_name(self):
        tests = (
            ('abc-def', 'AbcDef'),
            ('GhI', 'GhI'),
            ('jKlm.noP', 'JKlmNoP')
        )
        for t in tests:
            self.assertEqual(cf_safe_name(t[0]), t[1])

    def test_load_object_from_string(self):
        tests = (
            ('string.Template', string.Template),
            ('os.path.basename', os.path.basename),
            ('string.letters', string.letters)
        )
        for t in tests:
            self.assertIs(load_object_from_string(t[0]), t[1])

    def test_camel_to_snake(self):
        tests = (
            ('TestTemplate', 'test_template'),
            ('testTemplate', 'test_template'),
            ('test_Template', 'test__template'),
            ('testtemplate', 'testtemplate'),
        )
        for t in tests:
            self.assertEqual(camel_to_snake(t[0]), t[1])
