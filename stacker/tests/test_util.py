from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
import os
import string

import unittest
import mock

import boto3

from stacker.config import GitPackageSource
from stacker.exceptions import HookExecutionFailed
from stacker.hooks import Hook
from stacker.util import (
    cf_safe_name,
    load_object_from_string,
    camel_to_snake,
    merge_map,
    yaml_to_ordered_dict,
    get_client_region,
    get_s3_endpoint,
    s3_bucket_location_constraint,
    parse_cloudformation_template,
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

    def test_load_object_from_string(self):
        tests = (
            ("string.Template", string.Template),
            ("os.path.basename", os.path.basename),
            ("string.ascii_letters", string.ascii_letters)
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
        self.assertEqual(list(config['pre_build'].keys())[0], 'hook2')
        self.assertEqual(config['pre_build']['hook2']['path'], 'foo.bar')

    def test_get_client_region(self):
        regions = ["us-east-1", "us-west-1", "eu-west-1", "sa-east-1"]
        for region in regions:
            client = boto3.client("s3", region_name=region)
            self.assertEqual(get_client_region(client), region)

    def test_get_s3_endpoint(self):
        endpoint_url = "https://example.com"
        client = boto3.client("s3", region_name="us-east-1",
                              endpoint_url=endpoint_url)
        self.assertEqual(get_s3_endpoint(client), endpoint_url)

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

    def test_parse_cloudformation_template(self):
        template = """AWSTemplateFormatVersion: "2010-09-09"
Parameters:
  Param1:
    Type: String
Resources:
  Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName:
        !Join
          - "-"
          - - !Ref "AWS::StackName"
            - !Ref "AWS::Region"
Outputs:
  DummyId:
    Value: dummy-1234"""
        parsed_template = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Outputs': {'DummyId': {'Value': 'dummy-1234'}},
            'Parameters': {'Param1': {'Type': 'String'}},
            'Resources': {
                'Bucket': {'Type': 'AWS::S3::Bucket',
                           'Properties': {
                               'BucketName': {
                                   u'Fn::Join': [
                                       '-',
                                       [{u'Ref': u'AWS::StackName'},
                                        {u'Ref': u'AWS::Region'}]
                                   ]
                               }
                           }}
            }
        }
        self.assertEqual(
            parse_cloudformation_template(template),
            parsed_template
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
                b'857b4834980e582874d70feef77bb064b60762d1'
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


mock_hook = mock.Mock()


class TestHooks(unittest.TestCase):

    def setUp(self):
        self.context = mock_context(namespace="namespace")
        self.provider = mock_provider(region="us-east-1")

        global mock_hook
        mock_hook = mock.Mock()

    def test_missing_required_hook(self):
        hook = Hook("test", path="not.a.real.path", required=True)

        with self.assertRaises(HookExecutionFailed) as raised:
            hook.run(self.provider, self.context)
            self.assertIsInstance(ImportError, raised.exception.exception)

    def test_missing_required_hook_method(self):
        hook = Hook("test", path="stacker.hooks.blah", required=True)

        with self.assertRaises(HookExecutionFailed) as raised:
            hook.run(self.provider, self.context)
            self.assertIsInstance(AttributeError, raised.exception.exception)

    def test_missing_non_required_hook_method(self):
        hook = Hook("test", path="stacker.hooks.blah", required=False)

        result = hook.run(self.provider, self.context)
        self.assertIsNone(result)

    def test_default_required_hook(self):
        hook = Hook("test", path="stacker.hooks.blah")

        with self.assertRaises(HookExecutionFailed) as raised:
            hook.run(self.provider, self.context)
            self.assertIsInstance(AttributeError, raised.exception.exception)

    def test_valid_enabled_hook(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    required=True, enabled=True)

        result = mock_hook.return_value = mock.Mock()
        self.assertIs(result, hook.run(self.provider, self.context))
        mock_hook.assert_called_once()

    def test_valid_disabled_hook(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    required=True, enabled=False)

        self.assertIsNone(hook.run(self.provider, self.context))
        mock_hook.assert_not_called()

    def test_context_provided_to_hook(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    required=True)

        def return_context(*args, **kwargs):
            return kwargs['context']

        mock_hook.side_effect = return_context
        result = hook.run(self.provider, self.context)
        self.assertIs(result, self.context)

    def test_hook_failure(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    required=True)

        err = Exception()
        mock_hook.side_effect = err

        with self.assertRaises(HookExecutionFailed) as raised:
            hook.run(self.provider, self.context)
            self.assertIs(hook, raised.exception.hook)
            self.assertIs(err, raised.exception.exception)

    def test_hook_failure_skip(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    required=False)

        mock_hook.side_effect = Exception()
        result = hook.run(self.provider, self.context)
        self.assertIsNone(result)

    def test_return_data_hook(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    data_key='test')
        hook_data = {'hello': 'world'}
        mock_hook.return_value = hook_data

        result = hook.run(self.provider, self.context)
        self.assertEqual(hook_data, result)
        self.assertEqual(hook_data, self.context.hook_data.get('test'))

    def test_return_data_hook_duplicate_key(self):
        hook = Hook("test", path="stacker.tests.test_util.mock_hook",
                    data_key='test')
        mock_hook.return_value = {'foo': 'bar'}

        hook_data = {'hello': 'world'}
        self.context.set_hook_data('test', hook_data)
        with self.assertRaises(KeyError):
            hook.run(self.provider, self.context)

        self.assertEqual(hook_data, self.context.hook_data['test'])


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
