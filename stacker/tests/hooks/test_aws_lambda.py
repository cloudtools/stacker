from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import range
import os.path
import os
import mock
import random
from io import BytesIO as StringIO
from zipfile import ZipFile

import boto3
import botocore
import pytest
from moto import mock_s3
from troposphere.awslambda import Code

from stacker.hooks.aws_lambda import (
    ZIP_PERMS_MASK,
    _calculate_hash,
    _calculate_prebuilt_hash,
    select_bucket_region,
    upload_lambda_functions,
)
from ..factories import mock_context, mock_provider


REGION = "us-east-1"


@pytest.fixture
def all_files(tmpdir):
    files = (
        'f1/f1.py',
        'f1/f1.pyc',
        'f1/__init__.py',
        'f1/test/__init__.py',
        'f1/test/f1.py',
        'f1/test/f1.pyc',
        'f1/test2/test.txt',
        'f2/f2.js'
    )

    def create():
        for file in files:
            f = tmpdir.join(file)
            f.write(b'', ensure=True)
            yield f

    return list(create())


@pytest.fixture
def f1_files(tmpdir, all_files):
    return [p for p in all_files if p.relto(tmpdir).startswith('f1')]


@pytest.fixture
def f2_files(tmpdir, all_files):
    return [p for p in all_files if p.relto(tmpdir).startswith('f2')]


@pytest.fixture(scope='package')
def prebuilt_zip(stacker_fixture_dir):
    path = stacker_fixture_dir.join('test.zip')
    content = path.read_binary()
    md5 = 'c6fb602d9bde5a522856adabe9949f63'
    return dict(path=path, md5=md5, contents=content)


@pytest.fixture(autouse=True)
def s3():
    with mock_s3():
        yield boto3.client('s3', region_name=REGION)


def assert_s3_zip_file_list(s3, bucket, key, files, root=None):
    object_info = s3.get_object(Bucket=bucket, Key=key)
    zip_data = StringIO(object_info['Body'].read())

    expected_files = set()
    for f in files:
        rel_path = os.path.relpath(str(f), root) if root else str(f)
        expected_files.add(rel_path)

    found_files = set()
    with ZipFile(zip_data, 'r') as zip_file:
        for zip_info in zip_file.infolist():
            perms = (zip_info.external_attr & ZIP_PERMS_MASK) >> 16
            assert perms in (0o755, 0o644)
            found_files.add(zip_info.filename)

    assert found_files == set(expected_files)


def assert_s3_zip_contents(s3, bucket, key, contents):
    object_info = s3.get_object(Bucket=bucket, Key=key)
    zip_data = object_info['Body'].read()

    assert zip_data == contents


def assert_s3_bucket(s3, bucket, present=True):
    try:
        s3.head_bucket(Bucket=bucket)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            if present:
                pytest.fail('s3: bucket {} does not exist'.format(bucket))
        else:
            raise
    else:
        if not present:
            pytest.fail('s3: bucket {} should not exist'.format(bucket))


@pytest.fixture
def context():
    return mock_context()


@pytest.fixture
def provider():
    return mock_provider(region=REGION)


@pytest.fixture
def run_hook(context, provider):
    def run(**kwargs):
        return upload_lambda_functions(context=context, provider=provider,
                                       **kwargs)

    return run


def test_bucket_default(s3, context, run_hook):
    result = run_hook(functions={})
    assert result is not None

    assert_s3_bucket(s3, context.bucket_name, present=True)


def test_bucket_custom(s3, context, run_hook):
    result = run_hook(bucket='custom', functions={})
    assert result is not None

    assert_s3_bucket(s3, context.bucket_name, present=False)
    assert_s3_bucket(s3, 'custom', present=True)


def test_prefix(tmpdir, s3, all_files, f1_files, run_hook):
    root = tmpdir.join('f1')
    results = run_hook(
        prefix='cloudformation-custom-resources/',
        functions={
            'MyFunction': {
                'path': str(root)
            }
        })
    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, f1_files, root=root)
    assert code.S3Key.startswith(
        'cloudformation-custom-resources/lambda-MyFunction-')


def test_prefix_missing(tmpdir, s3, all_files, f1_files, run_hook):
    root = tmpdir.join('f1')
    results = run_hook(
        functions={
            'MyFunction': {
                'path': str(root)
            }
        }
    )

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, f1_files,
                            root=root)
    assert code.S3Key.startswith('lambda-MyFunction-')


def test_path_missing(run_hook):
    msg = "missing required property 'path' in function 'MyFunction'"
    with pytest.raises(ValueError, match=msg):
        run_hook(
            functions={
                'MyFunction': {
                }
            }
        )


def test_path_non_zip_non_dir(tmpdir, all_files, run_hook):
    root = tmpdir
    msg = 'Path must be an existing ZIP file or directory'
    with pytest.raises(ValueError, match=msg):
        run_hook(
            functions={
                'MyFunction': {
                    'path': str(root.join('test.txt'))
                }
            }
        )


def test_path_relative(tmpdir, s3, run_hook):
    root = tmpdir
    root.join('test/test.py').write(b'', ensure=True)

    get_config_directory = 'stacker.hooks.aws_lambda.get_config_directory'
    with mock.patch(get_config_directory, return_value=str(root)) as m1:
        results = run_hook(
            functions={
                'MyFunction': {
                    'path': 'test'
                }
            }
        )

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, ['test.py'])


def test_path_home_relative(tmpdir, s3, run_hook):
    root = tmpdir
    test_path = '~/test'

    orig_expanduser = os.path.expanduser
    tmpdir.join('test.py').write(b'')

    def expanduser(path):
        return str(root) if path == test_path else orig_expanduser(path)

    with mock.patch('os.path.expanduser', side_effect=expanduser):
        results = run_hook(
            functions={
                'MyFunction': {
                    'path': test_path
                }
            }
        )

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, ['test.py'])


def test_multiple_functions(tmpdir, s3, all_files, f1_files, f2_files,
                            run_hook):
    root1 = tmpdir.join('f1')
    root2 = tmpdir.join('f2')
    results = run_hook(
        functions={
            'MyFunction': {
                'path': str(root1)
            },
            'OtherFunction': {
                'path': str(root2)
            }
        }
    )

    assert results is not None

    f1_code = results.get('MyFunction')
    assert isinstance(f1_code, Code)
    assert_s3_zip_file_list(s3, f1_code.S3Bucket, f1_code.S3Key, f1_files,
                            root=root1)

    f2_code = results.get('OtherFunction')
    assert isinstance(f2_code, Code)
    assert_s3_zip_file_list(s3, f2_code.S3Bucket, f2_code.S3Key, f2_files,
                            root=root2)


def test_patterns_invalid(tmpdir, run_hook):
    root = tmpdir

    msg = ("Invalid file patterns in key 'include': must be a string or "
           'list of strings')
    with pytest.raises(ValueError, match=msg):
        run_hook(
            functions={
                'MyFunction': {
                    'path': str(root),
                    'include': {'invalid': 'invalid'}
                }
            }
        )


def test_patterns_include(tmpdir, s3, all_files, run_hook):
    root = tmpdir.join('f1')
    results = run_hook(
        functions={
            'MyFunction': {
                'path': str(root),
                'include': ['*.py', 'test2/']
            }
        }
    )

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, [
        'f1.py',
        '__init__.py',
        'test/__init__.py',
        'test/f1.py',
        'test2/test.txt'
    ])


def test_patterns_exclude(tmpdir, s3, all_files, run_hook):
    root = tmpdir.join('f1')
    results = run_hook(
        functions={
            'MyFunction': {
                'path': str(root),
                'exclude': ['*.pyc', 'test/']
            }
        }
    )

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, [
        'f1.py',
        '__init__.py',
        'test2/test.txt'
    ])


@mock_s3
def test_patterns_include_exclude(tmpdir, s3, all_files, run_hook):
    root = tmpdir.join('f1')
    results = run_hook(functions={
        'MyFunction': {
            'path': str(root),
            'include': '*.py',
            'exclude': 'test/'
        }
    })

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, [
        'f1.py',
        '__init__.py'
    ])


def test_patterns_exclude_all(tmpdir, all_files, run_hook):
    root = tmpdir.join('f1')

    msg = ('Empty list of files for Lambda payload. Check your '
           'include/exclude options for errors.')
    with pytest.raises(RuntimeError, match=msg):
        run_hook(
            functions={
                'MyFunction': {
                    'path': str(root),
                    'exclude': ['**']
                }
            }
        )


def test_idempotence(tmpdir, s3, all_files, run_hook):
    root = tmpdir.join('f1')

    bucket_name = 'test'
    functions = {
        'MyFunction': {
            'path': str(root)
        }
    }

    s3.create_bucket(Bucket=bucket_name)

    previous = None
    for i in range(2):
        results = run_hook(bucket=bucket_name, functions=functions)
        assert results is not None

        code = results.get('MyFunction')
        assert isinstance(code, Code)

        if not previous:
            previous = code.S3Key
            continue

        assert previous == code.S3Key


def test_calculate_hash(tmpdir, all_files, f1_files, f2_files):
    root = tmpdir

    all_hash_1 = _calculate_hash(map(str, all_files), str(root))
    all_hash_2 = _calculate_hash(map(str, all_files), str(root))
    f1_hash = _calculate_hash(map(str, f1_files), str(root))
    f2_hash = _calculate_hash(map(str, f2_files), str(root))

    assert all_hash_1 == all_hash_2
    assert f1_hash != all_hash_1
    assert f2_hash != all_hash_1
    assert f1_hash != f2_hash


def test_calculate_hash_diff_filename_same_contents(tmpdir, all_files):
    root = tmpdir

    files = all_files[:2]
    tmpdir.join(files[0]).write('data', ensure=True)
    tmpdir.join(files[1]).write('data', ensure=True)

    hash1 = _calculate_hash([str(files[0])], str(root))
    hash2 = _calculate_hash([str(files[1])], str(root))

    assert hash1 != hash2


def test_calculate_hash_different_ordering(tmpdir, all_files):
    root = tmpdir

    all_files_diff_order = random.sample(all_files, k=len(all_files))
    hash1 = _calculate_hash(map(str, all_files), str(root))
    hash2 = _calculate_hash(map(str, all_files_diff_order), str(root))
    assert hash1 == hash2


@pytest.mark.parametrize(
    'case',
    [
        dict(
            custom_bucket="myBucket",
            hook_region="us-east-1",
            stacker_bucket_region="us-west-1",
            provider_region="eu-west-1",
            result="us-east-1"
        ),
        dict(
            custom_bucket="myBucket",
            hook_region=None,
            stacker_bucket_region="us-west-1",
            provider_region="eu-west-1",
            result="eu-west-1"),
        dict(
            custom_bucket=None,
            hook_region="us-east-1",
            stacker_bucket_region="us-west-1",
            provider_region="eu-west-1",
            result="us-west-1"),
        dict(
            custom_bucket=None,
            hook_region="us-east-1",
            stacker_bucket_region=None,
            provider_region="eu-west-1",
            result="eu-west-1")
    ]
)
def test_select_bucket_region(case):
    result = case.pop('result')
    assert select_bucket_region(**case) == result


def test_follow_symlink_nonbool(run_hook):
    msg = "follow_symlinks option must be a boolean"
    with pytest.raises(ValueError, match=msg):
        run_hook(
            follow_symlinks="raiseValueError",
            functions={
                'MyFunction': {
                }
            }
        )


@pytest.fixture
def linked_dir(tmpdir):
    linked_dir = tmpdir.join('linked')
    linked_dir.mksymlinkto(tmpdir.join('f1'))
    return linked_dir


def test_follow_symlink_true(tmpdir, s3, all_files, f1_files, run_hook,
                             linked_dir):
    root = tmpdir
    results = run_hook(
        follow_symlinks=True,
        functions={
            'MyFunction': {
                'path': str(root)
            }
        }
    )
    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)

    linked_files = [p for p in linked_dir.visit() if p.check(file=1)]
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key,
                            all_files + linked_files, root=tmpdir)


def test_follow_symlink_false(tmpdir, s3, all_files, run_hook, linked_dir):
    root = tmpdir
    results = run_hook(
        follow_symlinks=False,
        functions={
            'MyFunction': {
                'path': str(root)
            }
        }
    )
    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_file_list(s3, code.S3Bucket, code.S3Key, all_files,
                            root=tmpdir)


def test_calculate_prebuilt_hash(prebuilt_zip):
    with open(prebuilt_zip['path'], 'rb') as f:
        generated_md5 = _calculate_prebuilt_hash(f)

    assert generated_md5 == prebuilt_zip['md5']


def test_upload_prebuilt_zip(s3, run_hook, prebuilt_zip):
    results = run_hook(functions={
        'MyFunction': {
            'path': prebuilt_zip['path']
        }
    })

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)

    assert_s3_zip_contents(s3, code.S3Bucket, code.S3Key,
                           prebuilt_zip['contents'])
    expected_basename = \
        'lambda-MyFunction-{}.zip'.format(prebuilt_zip['md5'])
    assert os.path.basename(code.S3Key) == expected_basename


def test_upload_prebuilt_zip_with_version(s3, run_hook, prebuilt_zip):
    version = '1.0.0'
    results = run_hook(
        functions={
            'MyFunction': {
                'path': prebuilt_zip['path'],
                'version': version
            }
        }
    )

    assert results is not None

    code = results.get('MyFunction')
    assert isinstance(code, Code)
    assert_s3_zip_contents(s3, code.S3Bucket, code.S3Key,
                           prebuilt_zip['contents'])

    expected_basename = 'lambda-MyFunction-1.0.0.zip'
    assert os.path.basename(code.S3Key) == expected_basename
