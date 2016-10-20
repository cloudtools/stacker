import os
import os.path
import stat
import logging
import hashlib
from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED

import boto3
import botocore
import formic
from troposphere.awslambda import Code

from stacker.util import get_config_directory


# UNIX file attributes are stored in the upper 16 bits in the external
# attributes field of a ZIP entry
ZIP_PERMS_MASK = (stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO) << 16

logger = logging.getLogger(__name__)


def _zip_files(files, root):
    """
    Generate a ZIP file in-memory containing the chosen files, specified
    relative to the root (and stored with those same relative paths in the
    ZIP).
    Normalizes UNIX permissions to avoid any problems with Lambda execution.

    Returns the contents as a string.
    """
    zip_data = StringIO()
    with ZipFile(zip_data, 'w', ZIP_DEFLATED) as zip_file:
        for fname in files:
            zip_file.write(os.path.join(root, fname), fname)

        # Fix file permissions to avoid any issues - only care whether a file
        # is executable or not, choosing between modes 755 and 644 accordingly.
        for zip_entry in zip_file.filelist:
            perms = (zip_entry.external_attr & ZIP_PERMS_MASK) >> 16
            if perms & stat.S_IXUSR != 0:
                new_perms = 0755
            else:
                new_perms = 0644

            if new_perms != perms:
                logger.debug("lambda: fixing perms: %s: %o => %o",
                             zip_entry.filename, perms, new_perms)
                new_attr = ((zip_entry.external_attr & ~ZIP_PERMS_MASK) |
                            (new_perms << 16))
                zip_entry.external_attr = new_attr

    contents = zip_data.getvalue()
    zip_data.close()

    return contents


def _find_files(root, includes, excludes):
    """
    Generate a list of files relative to a root path, applying inclusion and
    exclusion patterns. The documentation for the patterns can be found at:
    http://www.aviser.asia/formic/doc/index.html
    """

    root = os.path.abspath(root)
    file_set = formic.FileSet(directory=root, include=includes,
                              exclude=excludes)
    for filename in file_set.qualified_files(absolute=False):
        yield filename


def _zip_from_file_patterns(root, includes, excludes):
    """Generates a ZIP file from file patterns relative to a root path"""
    logger.info('lambda: base directory: %s', root)

    files = list(_find_files(root, includes, excludes))
    if not files:
        raise RuntimeError('Empty list of files for Lambda payload. Check '
                           'your include/exclude options for errors.')

    logger.info('lambda: adding %d files:', len(files))

    for fname in files:
        logger.info('lambda: + %s', fname)

    return _zip_files(files, root)


def _head_object(s3_conn, bucket, key):
    """Retrieve information about an object in S3, if it exists"""
    try:
        return s3_conn.head_object(Bucket=bucket, Key=key)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise


def _ensure_bucket(s3_conn, bucket):
    """Create an S3 bucket if it doesn't already exist"""
    try:
        s3_conn.head_bucket(Bucket=bucket)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.info('Creating bucket %s.', bucket)
            s3_conn.create_bucket(Bucket=bucket)
        elif e.response['Error']['Code'] in ('401', '403'):
            logger.exception('Access denied for bucket %s.', bucket)
            raise
        else:
            logger.exception('Error creating bucket %s. Error %s', bucket,
                             e.response)


def _upload_code(s3_conn, bucket, name, contents):
    """
    Upload a ZIP file to S3 for use by Lambda.

    The file will be stored with it's MD5 appended to the key, to allow
    avoiding repeated uploads in subsequent runs with unchanged content.

    Returns a troposphere.aws_lambda.Code object containing the bucket and key
    used.
    """

    hsh = hashlib.md5(contents)
    logger.debug('lambda: ZIP hash: %s', hsh.hexdigest())

    key = 'lambda-{}-{}.zip'.format(name, hsh.hexdigest())

    info = _head_object(s3_conn, bucket, key)
    expected_etag = '"{}"'.format(hsh.hexdigest())

    if info and info['ETag'] == expected_etag:
        logger.info('lambda: object %s already exists, not uploading', key)
    else:
        logger.info('lambda: uploading object %s', key)
        s3_conn.put_object(Bucket=bucket, Key=key, Body=contents,
                           ContentType='application/zip',
                           ACL='authenticated-read')

    return Code(S3Bucket=bucket, S3Key=key)


def _check_pattern_list(patterns, key, default=None):
    """
    Checks whether a include/exclude configuration is valid.

    It can be a string or a list of strings (if defined).
    """
    if not patterns:
        return default

    if isinstance(patterns, basestring):
        return [patterns]

    if isinstance(patterns, list):
        if all(isinstance(p, basestring) for p in patterns):
            return patterns

    raise ValueError("Invalid file patterns in key '{}': must be a string or "
                     'list of strings'.format(key))


def _upload_function(s3_conn, bucket, name, options):
    """
    Processes and uploads a complete Lambda payload to S3.

    The `path` option is mandatory, and can be a relative or absolute path.
    In the former case, it is interpreted relative to the stacker configuration
    path.
    """
    try:
        root = options['path']
    except KeyError as e:
        raise ValueError(
            "missing required property '{}' in function '{}'".format(
                e.args[0], name))

    includes = _check_pattern_list(options.get('include'), 'include',
                                   default=['**'])
    excludes = _check_pattern_list(options.get('exclude'), 'exclude',
                                   default=[])

    logger.info('lambda: processing function %s', name)

    # os.path.join will ignore other parameters if the right-most one is an
    # absolute path, which is exactly what we want.
    if not os.path.isabs(root):
        root = os.path.abspath(os.path.join(get_config_directory(), root))
    zip_contents = _zip_from_file_patterns(root, includes, excludes)

    return _upload_code(s3_conn, bucket, name, zip_contents)


def upload_lambda_functions(region, namespace, mappings, parameters,
                            context=None, **kwargs):
    """
    Prepares and uploads one or more Lambda payloads to Amazon S3.

    Example configuration::

        pre_build:
          - path: stacker.hooks.aws_lambda.upload_lambda_functions
            required: true
            args:
              bucket: custom-bucket
              functions:
                MyFunction:
                  path: ./lambda_functions
                  include:
                    - '*.py'
                    - '*.txt'
                  exclude:
                    - '*.pyc'
                    - test/

    bucket:
        Defines a custom bucket to upload functions to.
        Omitting it will cause the default stacker bucket to be used.
    functions:
        Dictionary of function configurations. Multiple functions
        can be specified, and all of them will be processed. The keys will be
        used as the function names while uploading files and for referencing
        inside templates (see more below).
    function.path:
        Base directory of the Lambda function payload content.
        If it is not an absolute path, it will be considered relative to the
        stacker configuration file being used.
        Files found here will be added to the Lambda ZIP, according to the
        include/exclude patterns (if they are defined).

        The *contents* of the directory are used. So, for example, with the
        following directory structure::

            config.yml
            lambda_functions/my_function.py
            lambda_functions/my_lib.py

        Using ``lambda_functions`` as the base path will cause the ZIP to
        contain ``my_function.py`` and ``my_lib.py`` in it's root.
    function.include:
        Pattern or list of patterns of files to include in the payload.
        If provided, only files that match *and* do not match any exclude
        rules will be added to the payload.

        Omitting it is equivalent to accepting all files that are not
        otherwise excluded.
    function.exclude:
        Pattern or list of patterns of files to exclude from the payload.
        If provided, any files that match will be ignored, regardless of
        whether they match an inclusion pattern.

        Common ignored files are already excluded, such as most VCS information
        directories (``.git``, ``.svn``) , ``__pycache__``, ``.pyc`` files,
        etc.

    Patterns can be defined in similar manner to .gitignore files. They are
    interpreted relative to the base path (or, if no slashes are present, only
    to the last component of the path). See
    http://www.aviser.asia/formic/doc/index.html for more details.

    Payloads will be stored in the selected bucket with a name in the form
    ``lambda-{name}-{md5}.zip``, where {md5} is the checksum of the ZIP
    payload.

    Subsequent runs with unchanged contents will generate the same payload.
    In such cases, no upload will be made, an the existing object will be used.

    To refer to the uploaded payload information inside a blueprint, the
    ``context.hook_data`` dictionary should be used. A
    ``troposphere.awslambda.Code`` object is stored for each processed
    function.

    Example (using the hook configuration outlined above)::

        from troposphere.awslambda import Function
        from stacker.blueprints.base import Blueprint

        class LambdaBlueprint(Blueprint):
            def create_template(self):
                code = self.context.hook_data['lambda:MyFunction']

                self.template.add_resource(
                    Function(
                        'MyFunction',
                        Code=code,
                        Handler='my_function.handler',
                        Role='...',
                        Runtime='python2.7'
                    )
                )
    """
    if not context:
        raise RuntimeError('context not received in hook, '
                           'check if recent version of stacker is being used')

    bucket = kwargs.get('bucket')
    if not bucket:
        bucket = context.bucket_name
        logger.info('lambda: using default bucket from stacker: %s', bucket)
    else:
        logger.info('lambda: using custom bucket: %s', bucket)

    session = boto3.Session(region_name=region)
    s3_conn = session.client('s3')

    _ensure_bucket(s3_conn, bucket)

    results = {}
    for name, options in kwargs['functions'].items():
        results['lambda:' + name] = _upload_function(s3_conn, bucket, name,
                                                     options)

    return results
