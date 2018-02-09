import unittest

import string
import os
import Queue

import mock

import boto3

from stacker.config import Hook, GitPackageSource
from stacker.util import (
    cf_safe_name,
    get_template_file_format,
    load_object_from_string,
    camel_to_snake,
    handle_hooks,
    merge_map,
    yaml_to_ordered_dict,
    retry_with_backoff,
    get_client_region,
    get_s3_endpoint,
    s3_bucket_location_constraint,
    Extractor,
    TarExtractor,
    TarGzipExtractor,
    ZipExtractor,
    SourceProcessor
)

from .factories import (
    mock_context,
    mock_provider,
)

regions = ["us-east-1", "cn-north-1", "ap-northeast-1", "eu-west-1",
           "ap-southeast-1", "ap-southeast-2", "us-west-2", "us-gov-west-1",
           "us-west-1", "eu-central-1", "sa-east-1"]


def mock_create_cache_directories(self, **kwargs):
    # Don't actually need the directories created in testing
    return 1


class TestUtil(unittest.TestCase):

    def test_cf_safe_name(self):
        tests = (
            ("abc-def", "AbcDef"),
            ("GhI", "GhI"),
            ("jKlm.noP", "JKlmNoP")
        )
        for t in tests:
            self.assertEqual(cf_safe_name(t[0]), t[1])

    def test_get_template_file_format(self):
        tests = (
            ("~/foo.json", "json"),
            ("root/car.yaml", "yaml")
        )
        for t in tests:
            self.assertEqual(get_template_file_format(t[0]), t[1])
        with self.assertRaises(KeyError):
            get_template_file_format('somepath.dll')

    def test_load_object_from_string(self):
        tests = (
            ("string.Template", string.Template),
            ("os.path.basename", os.path.basename),
            ("string.letters", string.letters)
        )
        for t in tests:
            self.assertIs(load_object_from_string(t[0]), t[1])

    def test_camel_to_snake(self):
        tests = (
            ("TestTemplate", "test_template"),
            ("testTemplate", "test_template"),
            ("test_Template", "test__template"),
            ("testtemplate", "testtemplate"),
        )
        for t in tests:
            self.assertEqual(camel_to_snake(t[0]), t[1])

    def test_merge_map(self):
        tests = [
            # 2 lists of stacks defined
            [{'stacks': [{'stack1': {'variables': {'a': 'b'}}}]},
             {'stacks': [{'stack2': {'variables': {'c': 'd'}}}]},
             {'stacks': [
                 {'stack1': {
                     'variables': {
                         'a': 'b'}}},
                 {'stack2': {
                     'variables': {
                         'c': 'd'}}}]}],
            # A list of stacks combined with a higher precedence dict of stacks
            [{'stacks': [{'stack1': {'variables': {'a': 'b'}}}]},
             {'stacks': {'stack2': {'variables': {'c': 'd'}}}},
             {'stacks': {'stack2': {'variables': {'c': 'd'}}}}],
            # 2 dicts of stacks with non-overlapping variables merged
            [{'stacks': {'stack1': {'variables': {'a': 'b'}}}},
             {'stacks': {'stack1': {'variables': {'c': 'd'}}}},
             {'stacks': {
                 'stack1': {
                     'variables': {
                         'a': 'b',
                         'c': 'd'}}}}],
            # 2 dicts of stacks with overlapping variables merged
            [{'stacks': {'stack1': {'variables': {'a': 'b'}}}},
             {'stacks': {'stack1': {'variables': {'a': 'c'}}}},
             {'stacks': {'stack1': {'variables': {'a': 'c'}}}}],
        ]
        for t in tests:
            self.assertEqual(merge_map(t[0], t[1]), t[2])

    def test_yaml_to_ordered_dict(self):
        raw_config = """
        pre_build:
          hook2:
            path: foo.bar
          hook1:
            path: foo1.bar1
        """
        config = yaml_to_ordered_dict(raw_config)
        self.assertEqual(config['pre_build'].keys()[0], 'hook2')
        self.assertEqual(config['pre_build']['hook2']['path'], 'foo.bar')

    def test_get_client_region(self):
        regions = ["us-east-1", "us-west-1", "eu-west-1", "sa-east-1"]
        for region in regions:
            client = boto3.client("s3", region_name=region)
            self.assertEqual(get_client_region(client), region)

    def test_get_s3_endpoint(self):
        endpoint_map = {
            "us-east-1": "https://s3.amazonaws.com",
            "us-west-1": "https://s3.us-west-1.amazonaws.com",
            "eu-west-1": "https://s3.eu-west-1.amazonaws.com",
            "sa-east-1": "https://s3.sa-east-1.amazonaws.com",
        }

        for region in endpoint_map:
            client = boto3.client("s3", region_name=region)
            self.assertEqual(get_s3_endpoint(client), endpoint_map[region])

    def test_s3_bucket_location_constraint(self):
        tests = (
            ("us-east-1", ""),
            ("us-west-1", "us-west-1")
        )
        for region, result in tests:
            self.assertEqual(
                s3_bucket_location_constraint(region),
                result
            )

    def test_extractors(self):
        self.assertEqual(Extractor('test.zip').archive, 'test.zip')
        self.assertEqual(TarExtractor().extension(), '.tar')
        self.assertEqual(TarGzipExtractor().extension(), '.tar.gz')
        self.assertEqual(ZipExtractor().extension(), '.zip')
        for i in [TarExtractor(), ZipExtractor(), ZipExtractor()]:
            i.set_archive('/tmp/foo')
            self.assertEqual(i.archive.endswith(i.extension()), True)

    def test_SourceProcessor_helpers(self):
        with mock.patch.object(SourceProcessor,
                               'create_cache_directories',
                               new=mock_create_cache_directories):
            sp = SourceProcessor(sources={})

            self.assertEqual(
                sp.sanitize_git_path('git@github.com:foo/bar.git'),
                'git_github.com_foo_bar'
            )
            self.assertEqual(
                sp.sanitize_uri_path('http://example.com/foo/bar.gz@1'),
                'http___example.com_foo_bar.gz_1'
            )
            self.assertEqual(
                sp.sanitize_git_path('git@github.com:foo/bar.git', 'v1'),
                'git_github.com_foo_bar-v1'
            )

            for i in [GitPackageSource({'branch': 'foo'}), {'branch': 'foo'}]:
                self.assertEqual(
                    sp.determine_git_ls_remote_ref(i),
                    'refs/heads/foo'
                )
            for i in [{'uri': 'git@foo'}, {'tag': 'foo'}, {'commit': '1234'}]:
                self.assertEqual(
                    sp.determine_git_ls_remote_ref(GitPackageSource(i)),
                    'HEAD'
                )
                self.assertEqual(
                    sp.determine_git_ls_remote_ref(i),
                    'HEAD'
                )

            self.assertEqual(
                sp.git_ls_remote('https://github.com/remind101/stacker.git',
                                 'refs/heads/release-1.0'),
                '857b4834980e582874d70feef77bb064b60762d1'
            )

            bad_configs = [{'uri': 'x',
                            'commit': '1234',
                            'tag': 'v1',
                            'branch': 'x'},
                           {'uri': 'x', 'commit': '1234', 'tag': 'v1'},
                           {'uri': 'x', 'commit': '1234', 'branch': 'x'},
                           {'uri': 'x', 'tag': 'v1', 'branch': 'x'},
                           {'uri': 'x', 'commit': '1234', 'branch': 'x'}]
            for i in bad_configs:
                with self.assertRaises(ImportError):
                    sp.determine_git_ref(GitPackageSource(i))
                with self.assertRaises(ImportError):
                    sp.determine_git_ref(i)

            self.assertEqual(
                sp.determine_git_ref(
                    GitPackageSource({'uri': 'https://github.com/remind101/'
                                             'stacker.git',
                                      'branch': 'release-1.0'})),
                '857b4834980e582874d70feef77bb064b60762d1'
            )
            self.assertEqual(
                sp.determine_git_ref(
                    GitPackageSource({'uri': 'git@foo', 'commit': '1234'})),
                '1234'
            )
            self.assertEqual(
                sp.determine_git_ref({'uri': 'git@foo', 'commit': '1234'}),
                '1234'
            )
            self.assertEqual(
                sp.determine_git_ref(
                    GitPackageSource({'uri': 'git@foo', 'tag': 'v1.0.0'})),
                'v1.0.0'
            )
            self.assertEqual(
                sp.determine_git_ref({'uri': 'git@foo', 'tag': 'v1.0.0'}),
                'v1.0.0'
            )


hook_queue = Queue.Queue()


def mock_hook(*args, **kwargs):
    hook_queue.put(kwargs)
    return True


def fail_hook(*args, **kwargs):
    return None


def exception_hook(*args, **kwargs):
    raise Exception


def context_hook(*args, **kwargs):
    return "context" in kwargs


def result_hook(*args, **kwargs):
    return {"foo": "bar"}


class TestHooks(unittest.TestCase):

    def setUp(self):
        self.context = mock_context(namespace="namespace")
        self.provider = mock_provider(region="us-east-1")

    def test_empty_hook_stage(self):
        hooks = []
        handle_hooks("fake", hooks, self.provider, self.context)
        self.assertTrue(hook_queue.empty())

    def test_missing_required_hook(self):
        hooks = [Hook({"path": "not.a.real.path", "required": True})]
        with self.assertRaises(ImportError):
            handle_hooks("missing", hooks, self.provider, self.context)

    def test_missing_required_hook_method(self):
        hooks = [{"path": "stacker.hooks.blah", "required": True}]
        with self.assertRaises(AttributeError):
            handle_hooks("missing", hooks, self.provider, self.context)

    def test_missing_non_required_hook_method(self):
        hooks = [Hook({"path": "stacker.hooks.blah", "required": False})]
        handle_hooks("missing", hooks, self.provider, self.context)
        self.assertTrue(hook_queue.empty())

    def test_default_required_hook(self):
        hooks = [Hook({"path": "stacker.hooks.blah"})]
        with self.assertRaises(AttributeError):
            handle_hooks("missing", hooks, self.provider, self.context)

    def test_valid_hook(self):
        hooks = [
            Hook({"path": "stacker.tests.test_util.mock_hook",
                  "required": True})]
        handle_hooks("missing", hooks, self.provider, self.context)
        good = hook_queue.get_nowait()
        self.assertEqual(good["provider"].region, "us-east-1")
        with self.assertRaises(Queue.Empty):
            hook_queue.get_nowait()

    def test_context_provided_to_hook(self):
        hooks = [
            Hook({"path": "stacker.tests.test_util.context_hook",
                  "required": True})]
        handle_hooks("missing", hooks, "us-east-1", self.context)

    def test_hook_failure(self):
        hooks = [
            Hook({"path": "stacker.tests.test_util.fail_hook",
                  "required": True})]
        with self.assertRaises(SystemExit):
            handle_hooks("fail", hooks, self.provider, self.context)
        hooks = [{"path": "stacker.tests.test_util.exception_hook",
                  "required": True}]
        with self.assertRaises(Exception):
            handle_hooks("fail", hooks, self.provider, self.context)
        hooks = [
            Hook({"path": "stacker.tests.test_util.exception_hook",
                  "required": False})]
        # Should pass
        handle_hooks("ignore_exception", hooks, self.provider, self.context)

    def test_return_data_hook(self):
        hooks = [
            Hook({
                "path": "stacker.tests.test_util.result_hook",
                "data_key": "my_hook_results"
            }),
            # Shouldn't return data
            Hook({
                "path": "stacker.tests.test_util.context_hook"
            })
        ]
        handle_hooks("result", hooks, "us-east-1", self.context)

        self.assertEqual(
            self.context.hook_data["my_hook_results"]["foo"],
            "bar"
        )
        # Verify only the first hook resulted in stored data
        self.assertEqual(
            self.context.hook_data.keys(), ["my_hook_results"]
        )

    def test_return_data_hook_duplicate_key(self):
        hooks = [
            Hook({
                "path": "stacker.tests.test_util.result_hook",
                "data_key": "my_hook_results"
            }),
            Hook({
                "path": "stacker.tests.test_util.result_hook",
                "data_key": "my_hook_results"
            })
        ]

        with self.assertRaises(KeyError):
            handle_hooks("result", hooks, "us-east-1", self.context)


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
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
        self.assertEqual(r, ["a", "b", "X", "Y"])
        self.assertEqual(self.counter, 1)

    def test_retry_exception(self):

        r = retry_with_backoff(self._works_second_attempt,
                               attempts=5, min_delay=0, max_delay=.1,
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
        self.assertEqual(r, ["a", "b", "X", "Y"])
        self.assertEqual(self.counter, 2)

    def test_multiple_exceptions(self):

        r = retry_with_backoff(self._second_raises_exception2,
                               exc_list=(TestException1, TestException2),
                               attempts=5, min_delay=0, max_delay=.1,
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
        self.assertEqual(r, ["a", "b", "X", "Y"])
        self.assertEqual(self.counter, 2)

    def test_unhandled_exception(self):

        with self.assertRaises(TestException2):
            retry_with_backoff(self._throws_exception2,
                               exc_list=(TestException1),
                               attempts=5, min_delay=0, max_delay=.1,
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
        self.assertEqual(self.counter, 1)

    def test_never_recovers(self):

        with self.assertRaises(TestException2):
            retry_with_backoff(self._throws_exception2,
                               exc_list=(TestException1, TestException2),
                               attempts=5, min_delay=0, max_delay=.1,
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
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
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
        self.assertEqual(self.counter, 2)
        self.assertEqual(r, ["a", "b", "X", "Y"])

        self.counter = 0
        with self.assertRaises(TestException2):
            retry_with_backoff(_throws_unhandled_exception,
                               exc_list=(TestException2),
                               retry_checker=_check_for_broke_message,
                               attempts=5, min_delay=0, max_delay=.1,
                               args=["a", "b"],
                               kwargs={"x": "X", "y": "Y"})
        self.assertEqual(self.counter, 1)
