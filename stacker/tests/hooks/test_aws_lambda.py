import os.path
import os
import unittest
import mock
import random
from StringIO import StringIO
from zipfile import ZipFile

import boto3
import botocore
from troposphere.awslambda import Code
from moto import mock_s3
from testfixtures import TempDirectory, ShouldRaise, compare

from stacker.context import Context
from stacker.hooks.aws_lambda import (
    upload_lambda_functions,
    ZIP_PERMS_MASK,
    _calculate_hash,
    select_bucket_region,
)
from ..factories import mock_provider


REGION = "us-east-1"
ALL_FILES = (
    'f1/f1.py',
    'f1/f1.pyc',
    'f1/__init__.py',
    'f1/test/__init__.py',
    'f1/test/f1.py',
    'f1/test/f1.pyc',
    'f1/test2/test.txt',
    'f2/f2.js'
)
F1_FILES = [p[3:] for p in ALL_FILES if p.startswith('f1')]
F2_FILES = [p[3:] for p in ALL_FILES if p.startswith('f2')]


class TestLambdaHooks(unittest.TestCase):
    @classmethod
    def temp_directory_with_files(cls, files=ALL_FILES):
        d = TempDirectory()
        for f in files:
            d.write(f, '')
        return d

    @property
    def s3(self):
        if not hasattr(self, '_s3'):
            self._s3 = boto3.client('s3', region_name=REGION)
        return self._s3

    def assert_s3_zip_file_list(self, bucket, key, files):
        object_info = self.s3.get_object(Bucket=bucket, Key=key)
        zip_data = StringIO(object_info['Body'].read())

        found_files = set()
        with ZipFile(zip_data, 'r') as zip_file:
            for zip_info in zip_file.infolist():
                perms = (zip_info.external_attr & ZIP_PERMS_MASK) >> 16
                self.assertIn(perms, (0755, 0644),
                              'ZIP member permission must be 755 or 644')
                found_files.add(zip_info.filename)

        compare(found_files, set(files))

    def assert_s3_bucket(self, bucket, present=True):
        try:
            self.s3.head_bucket(Bucket=bucket)
            if not present:
                self.fail('s3: bucket {} should not exist'.format(bucket))
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                if present:
                    self.fail('s3: bucket {} does not exist'.format(bucket))

    def setUp(self):
        self.context = Context(
            config={'namespace': 'test', 'stacker_bucket': 'test'})
        self.provider = mock_provider(region="us-east-1")

    def run_hook(self, **kwargs):
        real_kwargs = {
            'context': self.context,
            'provider': self.provider,
        }
        real_kwargs.update(kwargs)

        return upload_lambda_functions(**real_kwargs)

    @mock_s3
    def test_bucket_default(self):
        self.assertIsNotNone(
            self.run_hook(functions={}))

        self.assert_s3_bucket('test')

    @mock_s3
    def test_bucket_custom(self):
        self.assertIsNotNone(
            self.run_hook(bucket='custom', functions={}))

        self.assert_s3_bucket('test', present=False)
        self.assert_s3_bucket('custom')

    @mock_s3
    def test_prefix(self):
        with self.temp_directory_with_files() as d:
            results = self.run_hook(prefix='cloudformation-custom-resources/',
                                    functions={
                                        'MyFunction': {
                                            'path': d.path + '/f1'
                                        }
                                    })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, F1_FILES)
        self.assertTrue(code.S3Key.startswith(
            'cloudformation-custom-resources/lambda-MyFunction-'))

    @mock_s3
    def test_prefix_missing(self):
        with self.temp_directory_with_files() as d:
            results = self.run_hook(functions={
                'MyFunction': {
                    'path': d.path + '/f1'
                }
            })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, F1_FILES)
        self.assertTrue(code.S3Key.startswith('lambda-MyFunction-'))

    @mock_s3
    def test_path_missing(self):
        msg = "missing required property 'path' in function 'MyFunction'"
        with ShouldRaise(ValueError(msg)):
            self.run_hook(functions={
                'MyFunction': {
                }
            })

    @mock_s3
    def test_path_relative(self):
        get_config_directory = 'stacker.hooks.aws_lambda.get_config_directory'
        with self.temp_directory_with_files(['test/test.py']) as d, \
                mock.patch(get_config_directory) as m1:
            m1.return_value = d.path

            results = self.run_hook(functions={
                'MyFunction': {
                    'path': 'test'
                }
            })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, ['test.py'])

    @mock_s3
    def test_path_home_relative(self):
        test_path = '~/test'

        orig_expanduser = os.path.expanduser
        with self.temp_directory_with_files(['test.py']) as d, \
                mock.patch('os.path.expanduser') as m1:
            m1.side_effect = lambda p: (d.path if p == test_path
                                        else orig_expanduser(p))

            results = self.run_hook(functions={
                'MyFunction': {
                    'path': test_path
                }
            })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, ['test.py'])

    @mock_s3
    def test_multiple_functions(self):
        with self.temp_directory_with_files() as d:
            results = self.run_hook(functions={
                'MyFunction': {
                    'path': d.path + '/f1'
                },
                'OtherFunction': {
                    'path': d.path + '/f2'
                }
            })

        self.assertIsNotNone(results)

        f1_code = results.get('MyFunction')
        self.assertIsInstance(f1_code, Code)
        self.assert_s3_zip_file_list(f1_code.S3Bucket, f1_code.S3Key, F1_FILES)

        f2_code = results.get('OtherFunction')
        self.assertIsInstance(f2_code, Code)
        self.assert_s3_zip_file_list(f2_code.S3Bucket, f2_code.S3Key, F2_FILES)

    @mock_s3
    def test_patterns_invalid(self):
        msg = ("Invalid file patterns in key 'include': must be a string or "
               'list of strings')

        with ShouldRaise(ValueError(msg)):
            self.run_hook(functions={
                'MyFunction': {
                    'path': 'test',
                    'include': {'invalid': 'invalid'}
                }
            })

    @mock_s3
    def test_patterns_include(self):
        with self.temp_directory_with_files() as d:
            results = self.run_hook(functions={
                'MyFunction': {
                    'path': d.path + '/f1',
                    'include': ['*.py', 'test2/']
                }
            })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, [
            'f1.py',
            '__init__.py',
            'test/__init__.py',
            'test/f1.py',
            'test2/test.txt'
        ])

    @mock_s3
    def test_patterns_exclude(self):
        with self.temp_directory_with_files() as d:
            results = self.run_hook(functions={
                'MyFunction': {
                    'path': d.path + '/f1',
                    'exclude': ['*.pyc', 'test/']
                }
            })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, [
            'f1.py',
            '__init__.py',
            'test2/test.txt'
        ])

    @mock_s3
    def test_patterns_include_exclude(self):
        with self.temp_directory_with_files() as d:
            results = self.run_hook(functions={
                'MyFunction': {
                    'path': d.path + '/f1',
                    'include': '*.py',
                    'exclude': 'test/'
                }
            })

        self.assertIsNotNone(results)

        code = results.get('MyFunction')
        self.assertIsInstance(code, Code)
        self.assert_s3_zip_file_list(code.S3Bucket, code.S3Key, [
            'f1.py',
            '__init__.py'
        ])

    @mock_s3
    def test_patterns_exclude_all(self):
        msg = ('Empty list of files for Lambda payload. Check your '
               'include/exclude options for errors.')

        with self.temp_directory_with_files() as d, \
                ShouldRaise(RuntimeError(msg)):

            results = self.run_hook(functions={
                'MyFunction': {
                    'path': d.path + '/f1',
                    'exclude': ['**']
                }
            })

            self.assertIsNone(results)

    @mock_s3
    def test_idempotence(self):
        bucket_name = 'test'

        with self.temp_directory_with_files() as d:
            functions = {
                'MyFunction': {
                    'path': d.path + '/f1'
                }
            }

            self.s3.create_bucket(Bucket=bucket_name)

            previous = None
            for i in range(2):
                results = self.run_hook(bucket=bucket_name,
                                        functions=functions)
                self.assertIsNotNone(results)

                code = results.get('MyFunction')
                self.assertIsInstance(code, Code)

                if not previous:
                    previous = code.S3Key
                    continue

                compare(previous, code.S3Key,
                        prefix="zipfile name should not be modified in "
                               "repeated runs.")

    def test_calculate_hash(self):
        with self.temp_directory_with_files() as d1:
            root = d1.path
            hash1 = _calculate_hash(ALL_FILES, root)

        with self.temp_directory_with_files() as d2:
            root = d2.path
            hash2 = _calculate_hash(ALL_FILES, root)

        with self.temp_directory_with_files() as d3:
            root = d3.path
            with open(os.path.join(root, ALL_FILES[0]), "w") as fd:
                fd.write("modified file data")
            hash3 = _calculate_hash(ALL_FILES, root)

        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
        self.assertNotEqual(hash2, hash3)

    def test_calculate_hash_diff_filename_same_contents(self):
        files = ["file1.txt", "f2/file2.txt"]
        file1, file2 = files
        with TempDirectory() as d:
            root = d.path
            for fname in files:
                d.write(fname, "data")
            hash1 = _calculate_hash([file1], root)
            hash2 = _calculate_hash([file2], root)
        self.assertNotEqual(hash1, hash2)

    def test_calculate_hash_different_ordering(self):
        files1 = ALL_FILES
        files2 = random.sample(ALL_FILES, k=len(ALL_FILES))
        with TempDirectory() as d1:
            root1 = d1.path
            for fname in files1:
                d1.write(fname, "")
            with TempDirectory() as d2:
                root2 = d2.path
                for fname in files2:
                    d2.write(fname, "")
                hash1 = _calculate_hash(files1, root1)
                hash2 = _calculate_hash(files2, root2)
                self.assertEqual(hash1, hash2)

    def test_select_bucket_region(self):
        tests = (
            (("myBucket", "us-east-1", "us-west-1", "eu-west-1"), "us-east-1"),
            (("myBucket", None, "us-west-1", "eu-west-1"), "eu-west-1"),
            ((None, "us-east-1", "us-west-1", "eu-west-1"), "us-west-1"),
            ((None, "us-east-1", None, "eu-west-1"), "eu-west-1"),

        )

        for args, result in tests:
            self.assertEqual(select_bucket_region(*args), result)
