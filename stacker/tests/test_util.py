import unittest

import string
import os
import Queue

from stacker.context import Context
from stacker.util import (
    cf_safe_name, load_object_from_string,
    camel_to_snake, handle_hooks, retry_with_backoff)

regions = ['us-east-1', 'cn-north-1', 'ap-northeast-1', 'eu-west-1',
           'ap-southeast-1', 'ap-southeast-2', 'us-west-2', 'us-gov-west-1',
           'us-west-1', 'eu-central-1', 'sa-east-1']


class TestUtil(unittest.TestCase):

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

    def setUp(self):
        self.context = Context({'namespace': 'namespace'})

    def test_empty_hook_stage(self):
        hooks = []
        handle_hooks('fake', hooks, 'us-east-1', self.context)
        self.assertTrue(hook_queue.empty())

    def test_missing_required_hook(self):
        hooks = [{'path': 'not.a.real.path', 'required': True}]
        with self.assertRaises(ImportError):
            handle_hooks('missing', hooks, 'us-east-1', self.context)

    def test_missing_required_hook_method(self):
        hooks = [{'path': 'stacker.hooks.blah', 'required': True}]
        with self.assertRaises(AttributeError):
            handle_hooks('missing', hooks, 'us-east-1', self.context)

    def test_missing_non_required_hook_method(self):
        hooks = [{'path': 'stacker.hooks.blah', 'required': False}]
        handle_hooks('missing', hooks, 'us-east-1', self.context)
        self.assertTrue(hook_queue.empty())

    def test_default_required_hook(self):
        hooks = [{'path': 'stacker.hooks.blah'}]
        with self.assertRaises(AttributeError):
            handle_hooks('missing', hooks, 'us-east-1', self.context)

    def test_valid_hook(self):
        hooks = [{'path': 'stacker.tests.test_util.mock_hook',
                  'required': True}]
        handle_hooks('missing', hooks, 'us-east-1', self.context)
        good = hook_queue.get_nowait()
        self.assertEqual(good[0], 'us-east-1')
        with self.assertRaises(Queue.Empty):
            hook_queue.get_nowait()

    def test_hook_failure(self):
        hooks = [{'path': 'stacker.tests.test_util.fail_hook',
                  'required': True}]
        with self.assertRaises(SystemExit):
            handle_hooks('fail', hooks, 'us-east-1', self.context)
        hooks = [{'path': 'stacker.tests.test_util.exception_hook',
                  'required': True}]
        with self.assertRaises(Exception):
            handle_hooks('fail', hooks, 'us-east-1', self.context)
        hooks = [{'path': 'stacker.tests.test_util.exception_hook',
                  'required': False}]
        # Should pass
        handle_hooks('ignore_exception', hooks, 'us-east-1', self.context)


class TestException1(Exception):
    pass


class TestException2(Exception):
    pass


class TestExceptionRetries(unittest.TestCase):
    def setUp(self):
        self.counter = 0

    def _works_immediately(self, a, b, x=None, y=None):
        self.counter += 1
        return [a, b, x, y]

    def _works_second_attempt(self, a, b, x=None, y=None):
        self.counter += 1
        if self.counter == 2:
            return [a, b, x, y]
        raise Exception("Broke.")

    def _second_raises_exception2(self, a, b, x=None, y=None):
        self.counter += 1
        if self.counter == 2:
            return [a, b, x, y]
        raise TestException2("Broke.")

    def _throws_exception2(self, a, b, x=None, y=None):
        self.counter += 1
        raise TestException2("Broke.")

    def test_function_works_no_retry(self):

        r = retry_with_backoff(self._works_immediately,
                               attempts=2, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(r, ['a', 'b', 'X', 'Y'])
        self.assertEqual(self.counter, 1)

    def test_retry_exception(self):

        r = retry_with_backoff(self._works_second_attempt,
                               attempts=5, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(r, ['a', 'b', 'X', 'Y'])
        self.assertEqual(self.counter, 2)

    def test_multiple_exceptions(self):

        r = retry_with_backoff(self._second_raises_exception2,
                               exc_list=(TestException1, TestException2),
                               attempts=5, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(r, ['a', 'b', 'X', 'Y'])
        self.assertEqual(self.counter, 2)

    def test_unhandled_exception(self):

        with self.assertRaises(TestException2):
            retry_with_backoff(self._throws_exception2,
                               exc_list=(TestException1),
                               attempts=5, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(self.counter, 1)

    def test_never_recovers(self):

        with self.assertRaises(TestException2):
            retry_with_backoff(self._throws_exception2,
                               exc_list=(TestException1, TestException2),
                               attempts=5, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(self.counter, 5)

    def test_retry_checker(self):
        def _throws_handled_exception(a, b, x=None, y=None):
            self.counter += 1
            if self.counter == 2:
                return [a, b, x, y]
            raise TestException2("Broke.")

        def _throws_unhandled_exception(a, b, x=None, y=None):
            self.counter += 1
            if self.counter == 2:
                return [a, b, x, y]
            raise TestException2("Invalid")

        def _check_for_broke_message(e):
            if "Broke." in e.message:
                return True
            return False

        r = retry_with_backoff(_throws_handled_exception,
                               exc_list=(TestException2),
                               retry_checker=_check_for_broke_message,
                               attempts=5, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(self.counter, 2)
        self.assertEqual(r, ['a', 'b', 'X', 'Y'])

        self.counter = 0
        with self.assertRaises(TestException2):
            retry_with_backoff(_throws_unhandled_exception,
                               exc_list=(TestException2),
                               retry_checker=_check_for_broke_message,
                               attempts=5, min_delay=0, max_delay=.1,
                               args=['a', 'b'],
                               kwargs={'x': 'X', 'y': 'Y'})
        self.assertEqual(self.counter, 1)
