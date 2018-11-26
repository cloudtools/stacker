from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from past.builtins import basestring
import os
import os.path
import stat
import logging
import hashlib
from io import BytesIO as StringIO
from zipfile import ZipFile, ZIP_DEFLATED
import botocore
import formic
from troposphere.awslambda import Code
from stacker.session_cache import get_session

from stacker.util import (
    get_config_directory,
    ensure_s3_bucket,
)


"""Mask to retrieve only UNIX file permissions from the external attributes
field of a ZIP entry.
"""
ZIP_PERMS_MASK = (stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO) << 16

logger = logging.getLogger(__name__)


def _zip_files(files, root):
    """Generates a ZIP file in-memory from a list of files.

    Files will be stored in the archive with relative names, and have their
    UNIX permissions forced to 755 or 644 (depending on whether they are
    user-executable in the source filesystem).

    Args:
        files (list[str]): file names to add to the archive, relative to
            ``root``.
        root (str): base directory to retrieve files from.

    Returns:
        str: content of the ZIP file as a byte string.
        str: A calculated hash of all the files.

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
                new_perms = 0o755
            else:
                new_perms = 0o644

            if new_perms != perms:
                logger.debug("lambda: fixing perms: %s: %o => %o",
                             zip_entry.filename, perms, new_perms)
                new_attr = ((zip_entry.external_attr & ~ZIP_PERMS_MASK) |
                            (new_perms << 16))
                zip_entry.external_attr = new_attr

    contents = zip_data.getvalue()
    zip_data.close()
    content_hash = _calculate_hash(files, root)

    return contents, content_hash


def _calculate_hash(files, root):
    """ Returns a hash of all of the given files at the given root.

    Args:
        files (list[str]): file names to include in the hash calculation,
            relative to ``root``.
        root (str): base directory to analyze files in.

    Returns:
        str: A hash of the hashes of the given files.
    """
    file_hash = hashlib.md5()
    for fname in sorted(files):
        f = os.path.join(root, fname)
        file_hash.update((fname + "\0").encode())
        with open(f, "rb") as fd:
            for chunk in iter(lambda: fd.read(4096), ""):
                if not chunk:
                    break
                file_hash.update(chunk)
            file_hash.update("\0".encode())

    return file_hash.hexdigest()


def _find_files(root, includes, excludes, follow_symlinks):
    """List files inside a directory based on include and exclude rules.

    This is a more advanced version of `glob.glob`, that accepts multiple
    complex patterns.

    Args:
        root (str): base directory to list files from.
        includes (list[str]): inclusion patterns. Only files matching those
            patterns will be included in the result.
        excludes (list[str]): exclusion patterns. Files matching those
            patterns will be excluded from the result. Exclusions take
            precedence over inclusions.
        follow_symlinks (bool): If true, symlinks will be included in the
            resulting zip file

    Yields:
        str: a file name relative to the root.

    Note:
        Documentation for the patterns can be found at
        http://www.aviser.asia/formic/doc/index.html
    """

    root = os.path.abspath(root)
    file_set = formic.FileSet(
        directory=root, include=includes,
        exclude=excludes, symlinks=follow_symlinks,
    )

    for filename in file_set.qualified_files(absolute=False):
        yield filename


def _zip_from_file_patterns(root, includes, excludes, follow_symlinks):
    """Generates a ZIP file in-memory from file search patterns.

    Args:
        root (str): base directory to list files from.
        includes (list[str]): inclusion patterns. Only files  matching those
            patterns will be included in the result.
        excludes (list[str]): exclusion patterns. Files matching those
            patterns will be excluded from the result. Exclusions take
            precedence over inclusions.
        follow_symlinks (bool): If true, symlinks will be included in the
            resulting zip file

    See Also:
        :func:`_zip_files`, :func:`_find_files`.

    Raises:
        RuntimeError: when the generated archive would be empty.

    """
    logger.info('lambda: base directory: %s', root)

    files = list(_find_files(root, includes, excludes, follow_symlinks))
    if not files:
        raise RuntimeError('Empty list of files for Lambda payload. Check '
                           'your include/exclude options for errors.')

    logger.info('lambda: adding %d files:', len(files))

    for fname in files:
        logger.debug('lambda: + %s', fname)

    return _zip_files(files, root)


def _head_object(s3_conn, bucket, key):
    """Retrieve information about an object in S3 if it exists.

    Args:
        s3_conn (botocore.client.S3): S3 connection to use for operations.
        bucket (str): name of the bucket containing the key.
        key (str): name of the key to lookup.

    Returns:
        dict: S3 object information, or None if the object does not exist.
            See the AWS documentation for explanation of the contents.

    Raises:
        botocore.exceptions.ClientError: any error from boto3 other than key
            not found is passed through.
    """
    try:
        return s3_conn.head_object(Bucket=bucket, Key=key)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise


def _upload_code(s3_conn, bucket, prefix, name, contents, content_hash,
                 payload_acl):
    """Upload a ZIP file to S3 for use by Lambda.

    The key used for the upload will be unique based on the checksum of the
    contents. No changes will be made if the contents in S3 already match the
    expected contents.

    Args:
        s3_conn (botocore.client.S3): S3 connection to use for operations.
        bucket (str): name of the bucket to create.
        prefix (str): S3 prefix to prepend to the constructed key name for
            the uploaded file
        name (str): desired name of the Lambda function. Will be used to
            construct a key name for the uploaded file.
        contents (str): byte string with the content of the file upload.
        content_hash (str): md5 hash of the contents to be uploaded.
        payload_acl (str): The canned S3 object ACL to be applied to the
            uploaded payload

    Returns:
        troposphere.awslambda.Code: CloudFormation Lambda Code object,
        pointing to the uploaded payload in S3.

    Raises:
        botocore.exceptions.ClientError: any error from boto3 is passed
            through.
    """

    logger.debug('lambda: ZIP hash: %s', content_hash)
    key = '{}lambda-{}-{}.zip'.format(prefix, name, content_hash)

    if _head_object(s3_conn, bucket, key):
        logger.info('lambda: object %s already exists, not uploading', key)
    else:
        logger.info('lambda: uploading object %s', key)
        s3_conn.put_object(Bucket=bucket, Key=key, Body=contents,
                           ContentType='application/zip',
                           ACL=payload_acl)

    return Code(S3Bucket=bucket, S3Key=key)


def _check_pattern_list(patterns, key, default=None):
    """Validates file search patterns from user configuration.

    Acceptable input is a string (which will be converted to a singleton list),
    a list of strings, or anything falsy (such as None or an empty dictionary).
    Empty or unset input will be converted to a default.

    Args:
        patterns: input from user configuration (YAML).
        key (str): name of the configuration key the input came from,
            used for error display purposes.

    Keyword Args:
        default: value to return in case the input is empty or unset.

    Returns:
        list[str]: validated list of patterns

    Raises:
        ValueError: if the input is unacceptable.
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


def _upload_function(s3_conn, bucket, prefix, name, options, follow_symlinks,
                     payload_acl):
    """Builds a Lambda payload from user configuration and uploads it to S3.

    Args:
        s3_conn (botocore.client.S3): S3 connection to use for operations.
        bucket (str): name of the bucket to upload to.
        prefix (str): S3 prefix to prepend to the constructed key name for
            the uploaded file
        name (str): desired name of the Lambda function. Will be used to
            construct a key name for the uploaded file.
        options (dict): configuration for how to build the payload.
            Consists of the following keys:
                * path:
                    base path to retrieve files from (mandatory). If not
                    absolute, it will be interpreted as relative to the stacker
                    configuration file directory, then converted to an absolute
                    path. See :func:`stacker.util.get_config_directory`.
                * include:
                    file patterns to include in the payload (optional).
                * exclude:
                    file patterns to exclude from the payload (optional).
        follow_symlinks  (bool): If true, symlinks will be included in the
            resulting zip file
        payload_acl (str): The canned S3 object ACL to be applied to the
            uploaded payload

    Returns:
        troposphere.awslambda.Code: CloudFormation AWS Lambda Code object,
        pointing to the uploaded object in S3.

    Raises:
        ValueError: if any configuration is invalid.
        botocore.exceptions.ClientError: any error from boto3 is passed
            through.
    """
    try:
        root = os.path.expanduser(options['path'])
    except KeyError as e:
        raise ValueError(
            "missing required property '{}' in function '{}'".format(
                e.args[0], name))

    includes = _check_pattern_list(options.get('include'), 'include',
                                   default=['**'])
    excludes = _check_pattern_list(options.get('exclude'), 'exclude',
                                   default=[])

    logger.debug('lambda: processing function %s', name)

    # os.path.join will ignore other parameters if the right-most one is an
    # absolute path, which is exactly what we want.
    if not os.path.isabs(root):
        root = os.path.abspath(os.path.join(get_config_directory(), root))
    zip_contents, content_hash = _zip_from_file_patterns(root,
                                                         includes,
                                                         excludes,
                                                         follow_symlinks)

    return _upload_code(s3_conn, bucket, prefix, name, zip_contents,
                        content_hash, payload_acl)


def select_bucket_region(custom_bucket, hook_region, stacker_bucket_region,
                         provider_region):
    """Returns the appropriate region to use when uploading functions.

    Select the appropriate region for the bucket where lambdas are uploaded in.

    Args:
        custom_bucket (str, None): The custom bucket name provided by the
            `bucket` kwarg of the aws_lambda hook, if provided.
        hook_region (str): The contents of the `bucket_region` argument to
            the hook.
        stacker_bucket_region (str): The contents of the
            `stacker_bucket_region` global setting.
        provider_region (str): The region being used by the provider.

    Returns:
        str: The appropriate region string.
    """
    region = None
    if custom_bucket:
        region = hook_region
    else:
        region = stacker_bucket_region
    return region or provider_region


def upload_lambda_functions(context, provider, **kwargs):
    """Builds Lambda payloads from user configuration and uploads them to S3.

    Constructs ZIP archives containing files matching specified patterns for
    each function, uploads the result to Amazon S3, then stores objects (of
    type :class:`troposphere.awslambda.Code`) in the context's hook data,
    ready to be referenced in blueprints.

    Configuration consists of some global options, and a dictionary of function
    specifications. In the specifications, each key indicating the name of the
    function (used for generating names for artifacts), and the value
    determines what files to include in the ZIP (see more details below).

    Payloads are uploaded to either a custom bucket or stackers default bucket,
    with the key containing it's checksum, to allow repeated uploads to be
    skipped in subsequent runs.

    The configuration settings are documented as keyword arguments below.

    Keyword Arguments:
        bucket (str, optional): Custom bucket to upload functions to.
            Omitting it will cause the default stacker bucket to be used.
        bucket_region (str, optional): The region in which the bucket should
            exist. If not given, the region will be either be that of the
            global `stacker_bucket_region` setting, or else the region in
            use by the provider.
        prefix (str, optional): S3 key prefix to prepend to the uploaded
            zip name.
        follow_symlinks (bool, optional): Will determine if symlinks should
            be followed and included with the zip artifact. Default: False
        payload_acl (str, optional): The canned S3 object ACL to be applied to
            the uploaded payload. Default: private
        functions (dict):
            Configurations of desired payloads to build. Keys correspond to
            function names, used to derive key names for the payload. Each
            value should itself be a dictionary, with the following data:

                * path (str):

                    Base directory of the Lambda function payload content.
                    If it not an absolute path, it will be considered relative
                    to the directory containing the stacker configuration file
                    in use.

                    Files in this directory will be added to the payload ZIP,
                    according to the include and exclude patterns. If not
                    patterns are provided, all files in this directory
                    (respecting default exclusions) will be used.

                    Files are stored in the archive with path names relative to
                    this directory. So, for example, all the files contained
                    directly under this directory will be added to the root of
                    the ZIP file.

                * include(str or list[str], optional):

                    Pattern or list of patterns of files to include in the
                    payload. If provided, only files that match these
                    patterns will be included in the payload.

                    Omitting it is equivalent to accepting all files that are
                    not otherwise excluded.

                * exclude(str or list[str], optional):
                    Pattern or list of patterns of files to exclude from the
                    payload. If provided, any files that match will be ignored,
                    regardless of whether they match an inclusion pattern.

                    Commonly ignored files are already excluded by default,
                    such as ``.git``, ``.svn``, ``__pycache__``, ``*.pyc``,
                    ``.gitignore``, etc.

    Examples:
        .. Hook configuration.
        .. code-block:: yaml

            pre_build:
              - path: stacker.hooks.aws_lambda.upload_lambda_functions
                required: true
                enabled: true
                data_key: lambda
                args:
                  bucket: custom-bucket
                  follow_symlinks: true
                  prefix: cloudformation-custom-resources/
                  payload_acl: authenticated-read
                  functions:
                    MyFunction:
                      path: ./lambda_functions
                      include:
                        - '*.py'
                        - '*.txt'
                      exclude:
                        - '*.pyc'
                        - test/

        .. Blueprint usage
        .. code-block:: python

            from troposphere.awslambda import Function
            from stacker.blueprints.base import Blueprint

            class LambdaBlueprint(Blueprint):
                def create_template(self):
                    code = self.context.hook_data['lambda']['MyFunction']

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
    custom_bucket = kwargs.get('bucket')
    if not custom_bucket:
        bucket_name = context.bucket_name
        logger.info("lambda: using default bucket from stacker: %s",
                    bucket_name)
    else:
        bucket_name = custom_bucket
        logger.info("lambda: using custom bucket: %s", bucket_name)

    custom_bucket_region = kwargs.get("bucket_region")
    if not custom_bucket and custom_bucket_region:
        raise ValueError("Cannot specify `bucket_region` without specifying "
                         "`bucket`.")

    bucket_region = select_bucket_region(
        custom_bucket,
        custom_bucket_region,
        context.config.stacker_bucket_region,
        provider.region
    )

    # Check if we should walk / follow symlinks
    follow_symlinks = kwargs.get('follow_symlinks', False)
    if not isinstance(follow_symlinks, bool):
        raise ValueError('follow_symlinks option must be a boolean')

    # Check for S3 object acl. Valid values from:
    # https://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html#canned-acl
    payload_acl = kwargs.get('payload_acl', 'private')

    # Always use the global client for s3
    session = get_session(bucket_region)
    s3_client = session.client('s3')

    ensure_s3_bucket(s3_client, bucket_name, bucket_region)

    prefix = kwargs.get('prefix', '')

    results = {}
    for name, options in kwargs['functions'].items():
        results[name] = _upload_function(s3_client, bucket_name, prefix, name,
                                         options, follow_symlinks, payload_acl)

    return results
