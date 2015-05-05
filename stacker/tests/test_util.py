import unittest

import string
import os
import Queue

from stacker.util import (
    get_bucket_location, cf_safe_name, load_object_from_string,
    camel_to_snake, handle_hooks)

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


hook_queue = Queue.Queue()


def mock_hook(*args):
    hook_queue.put(args)
    return True


def fail_hook(*args):
    return None


def exception_hook(*args):
    raise Exception


class TestHooks(unittest.TestCase):
    def test_empty_hook_stage(self):
        hooks = []
        handle_hooks('fake', hooks, 'us-east-1', 'stage', {}, {})
        self.assertTrue(hook_queue.empty())

    def test_missing_required_hook(self):
        hooks = [{'path': 'not.a.real.path', 'required': True}]
        with self.assertRaises(ImportError):
            handle_hooks('missing', hooks, 'us-east-1', 'stage', {}, {})

    def test_missing_required_hook_method(self):
        hooks = [{'path': 'stacker.hooks.blah', 'required': True}]
        with self.assertRaises(AttributeError):
            handle_hooks('missing', hooks, 'us-east-1', 'stage', {}, {})

    def test_missing_non_required_hook_method(self):
        hooks = [{'path': 'stacker.hooks.blah', 'required': False}]
        handle_hooks('missing', hooks, 'us-east-1', 'stage', {}, {})
        self.assertTrue(hook_queue.empty())

    def test_default_required_hook(self):
        hooks = [{'path': 'stacker.hooks.blah'}]
        with self.assertRaises(AttributeError):
            handle_hooks('missing', hooks, 'us-east-1', 'stage', {}, {})

    def test_valid_hook(self):
        hooks = [{'path': 'stacker.tests.test_util.mock_hook',
                  'required': True}]
        handle_hooks('missing', hooks, 'us-east-1', 'stage', {}, {})
        good = hook_queue.get_nowait()
        self.assertEqual(good[0], 'us-east-1')
        with self.assertRaises(Queue.Empty):
            hook_queue.get_nowait()

    def test_hook_failure(self):
        hooks = [{'path': 'stacker.tests.test_util.fail_hook',
                  'required': True}]
        with self.assertRaises(SystemExit):
            handle_hooks('fail', hooks, 'us-east-1', 'stage', {}, {})
        hooks = [{'path': 'stacker.tests.test_util.exception_hook',
                  'required': True}]
        with self.assertRaises(Exception):
            handle_hooks('fail', hooks, 'us-east-1', 'stage', {}, {})
        hooks = [{'path': 'stacker.tests.test_util.exception_hook',
                  'required': False}]
        # Should pass
        handle_hooks('ignore_exception', hooks, 'us-east-1', 'stage', {}, {})
