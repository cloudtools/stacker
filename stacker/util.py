from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str
from builtins import object
import copy
import uuid
import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import collections
from collections import OrderedDict

import botocore.client
import botocore.exceptions
import dateutil
import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from .awscli_yamlhelper import yaml_parse
from stacker.session_cache import get_session

logger = logging.getLogger(__name__)


def camel_to_snake(name):
    """Converts CamelCase to snake_case.

    Args:
        name (string): The name to convert from CamelCase to snake_case.

    Returns:
        string: Converted string.
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def convert_class_name(kls):
    """Gets a string that represents a given class.

    Args:
        kls (class): The class being analyzed for its name.

    Returns:
        string: The name of the given kls.
    """
    return camel_to_snake(kls.__name__)


def parse_zone_id(full_zone_id):
    """Parses the returned hosted zone id and returns only the ID itself."""
    return full_zone_id.split("/")[2]


def get_hosted_zone_by_name(client, zone_name):
    """Get the zone id of an existing zone by name.

    Args:
        client (:class:`botocore.client.Route53`): The connection used to
            interact with Route53's API.
        zone_name (string): The name of the DNS hosted zone to create.

    Returns:
        string: The Id of the Hosted Zone.
    """
    p = client.get_paginator("list_hosted_zones")

    for i in p.paginate():
        for zone in i["HostedZones"]:
            if zone["Name"] == zone_name:
                return parse_zone_id(zone["Id"])
    return None


def get_or_create_hosted_zone(client, zone_name):
    """Get the Id of an existing zone, or create it.

    Args:
        client (:class:`botocore.client.Route53`): The connection used to
            interact with Route53's API.
        zone_name (string): The name of the DNS hosted zone to create.

    Returns:
        string: The Id of the Hosted Zone.
    """
    zone_id = get_hosted_zone_by_name(client, zone_name)
    if zone_id:
        return zone_id

    logger.debug("Zone %s does not exist, creating.", zone_name)

    reference = uuid.uuid4().hex

    response = client.create_hosted_zone(Name=zone_name,
                                         CallerReference=reference)

    return parse_zone_id(response["HostedZone"]["Id"])


class SOARecordText(object):
    """Represents the actual body of an SOARecord. """
    def __init__(self, record_text):
        (self.nameserver, self.contact, self.serial, self.refresh,
            self.retry, self.expire, self.min_ttl) = record_text.split()

    def __str__(self):
        return "%s %s %s %s %s %s %s" % (
            self.nameserver, self.contact, self.serial, self.refresh,
            self.retry, self.expire, self.min_ttl
        )


class SOARecord(object):
    """Represents an SOA record. """
    def __init__(self, record):
        self.name = record["Name"]
        self.text = SOARecordText(record["ResourceRecords"][0]["Value"])
        self.ttl = record["TTL"]


def get_soa_record(client, zone_id, zone_name):
    """Gets the SOA record for zone_name from zone_id.

    Args:
        client (:class:`botocore.client.Route53`): The connection used to
            interact with Route53's API.
        zone_id (string): The AWS Route53 zone id of the hosted zone to query.
        zone_name (string): The name of the DNS hosted zone to create.

    Returns:
        :class:`stacker.util.SOARecord`: An object representing the parsed SOA
            record returned from AWS Route53.
    """

    response = client.list_resource_record_sets(HostedZoneId=zone_id,
                                                StartRecordName=zone_name,
                                                StartRecordType="SOA",
                                                MaxItems="1")
    return SOARecord(response["ResourceRecordSets"][0])


def create_route53_zone(client, zone_name):
    """Creates the given zone_name if it doesn't already exists.

    Also sets the SOA negative caching TTL to something short (300 seconds).

    Args:
        client (:class:`botocore.client.Route53`): The connection used to
            interact with Route53's API.
        zone_name (string): The name of the DNS hosted zone to create.

    Returns:
        string: The zone id returned from AWS for the existing, or newly
            created zone.
    """
    if not zone_name.endswith("."):
        zone_name += "."
    zone_id = get_or_create_hosted_zone(client, zone_name)
    old_soa = get_soa_record(client, zone_id, zone_name)

    # If the negative cache value is already 300, don't update it.
    if old_soa.text.min_ttl == "300":
        return zone_id

    new_soa = copy.deepcopy(old_soa)
    logger.debug("Updating negative caching value on zone %s to 300.",
                 zone_name)
    new_soa.text.min_ttl = "300"
    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Comment": "Update SOA min_ttl to 300.",
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": zone_name,
                        "Type": "SOA",
                        "TTL": old_soa.ttl,
                        "ResourceRecords": [
                            {
                                "Value": str(new_soa.text)
                            }
                        ]
                    }
                },
            ]
        }
    )
    return zone_id


def load_object_from_string(fqcn):
    """Converts "." delimited strings to a python object.

    Given a "." delimited string representing the full path to an object
    (function, class, variable) inside a module, return that object.  Example:

    load_object_from_string("os.path.basename")
    load_object_from_string("logging.Logger")
    load_object_from_string("LocalClassName")
    """
    module_path = "__main__"
    object_name = fqcn
    if "." in fqcn:
        module_path, object_name = fqcn.rsplit(".", 1)
        importlib.import_module(module_path)
    return getattr(sys.modules[module_path], object_name)


def merge_map(a, b):
    """Recursively merge elements of argument b into argument a.

    Primarly used for merging two dictionaries together, where dict b takes
    precedence over dict a. If 2 lists are provided, they are concatenated.
    """
    if isinstance(a, list) and isinstance(b, list):
        return a + b

    if not isinstance(a, dict) or not isinstance(b, dict):
        return b

    for key in b:
        a[key] = merge_map(a[key], b[key]) if key in a else b[key]
    return a


def yaml_to_ordered_dict(stream, loader=yaml.SafeLoader):
    """Provides yaml.load alternative with preserved dictionary order.

    Args:
        stream (string): YAML string to load.
        loader (:class:`yaml.loader`): PyYAML loader class. Defaults to safe
            load.

    Returns:
        OrderedDict: Parsed YAML.
    """
    class OrderedUniqueLoader(loader):
        """
        Subclasses the given pyYAML `loader` class.

        Validates all sibling keys to insure no duplicates.

        Returns an OrderedDict instead of a Dict.
        """

        # keys which require no duplicate siblings.
        NO_DUPE_SIBLINGS = ["stacks", "class_path"]
        # keys which require no duplicate children keys.
        NO_DUPE_CHILDREN = ["stacks"]

        def _error_mapping_on_dupe(self, node, node_name):
            """check mapping node for dupe children keys."""
            if isinstance(node, MappingNode):
                mapping = {}
                for n in node.value:
                    a = n[0]
                    b = mapping.get(a.value, None)
                    if b:
                        msg = "{} mapping cannot have duplicate keys {} {}"
                        raise ConstructorError(
                            msg.format(node_name, b.start_mark, a.start_mark)
                        )
                    mapping[a.value] = a

        def _validate_mapping(self, node, deep=False):
            if not isinstance(node, MappingNode):
                raise ConstructorError(
                    None, None,
                    "expected a mapping node, but found %s" % node.id,
                    node.start_mark)
            mapping = OrderedDict()
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError as exc:
                    raise ConstructorError(
                        "while constructing a mapping", node.start_mark,
                        "found unhashable key (%s)" % exc, key_node.start_mark
                    )
                # prevent duplicate sibling keys for certain "keywords".
                if key in mapping and key in self.NO_DUPE_SIBLINGS:
                    msg = "{} key cannot have duplicate siblings {} {}"
                    raise ConstructorError(
                        msg.format(key, node.start_mark, key_node.start_mark)
                    )
                if key in self.NO_DUPE_CHILDREN:
                    # prevent duplicate children keys for this mapping.
                    self._error_mapping_on_dupe(value_node, key_node.value)
                value = self.construct_object(value_node, deep=deep)
                mapping[key] = value
            return mapping

        def construct_mapping(self, node, deep=False):
            """Override parent method to use OrderedDict."""
            if isinstance(node, MappingNode):
                self.flatten_mapping(node)
            return self._validate_mapping(node, deep=deep)

        def construct_yaml_map(self, node):
            data = OrderedDict()
            yield data
            value = self.construct_mapping(node)
            data.update(value)

    OrderedUniqueLoader.add_constructor(
        u'tag:yaml.org,2002:map', OrderedUniqueLoader.construct_yaml_map,
    )
    return yaml.load(stream, OrderedUniqueLoader)


def uppercase_first_letter(s):
    """Return string "s" with first character upper case."""
    return s[0].upper() + s[1:]


def cf_safe_name(name):
    """Converts a name to a safe string for a Cloudformation resource.

    Given a string, returns a name that is safe for use as a CloudFormation
    Resource. (ie: Only alphanumeric characters)
    """
    alphanumeric = r"[a-zA-Z0-9]+"
    parts = re.findall(alphanumeric, name)
    return "".join([uppercase_first_letter(part) for part in parts])


def handle_hooks(stage, hooks, provider, context):
    """ Used to handle pre/post_build hooks.

    These are pieces of code that we want to run before/after the builder
    builds the stacks.

    Args:
        stage (string): The current stage (pre_run, post_run, etc).
        hooks (list): A list of :class:`stacker.config.Hook` containing the
            hooks to execute.
        provider (:class:`stacker.provider.base.BaseProvider`): The provider
            the current stack is using.
        context (:class:`stacker.context.Context`): The current stacker
            context.
    """
    if not hooks:
        logger.debug("No %s hooks defined.", stage)
        return

    hook_paths = []
    for i, h in enumerate(hooks):
        try:
            hook_paths.append(h.path)
        except KeyError:
            raise ValueError("%s hook #%d missing path." % (stage, i))

    logger.info("Executing %s hooks: %s", stage, ", ".join(hook_paths))
    for hook in hooks:
        data_key = hook.data_key
        required = hook.required
        kwargs = hook.args or {}
        enabled = hook.enabled
        if not enabled:
            logger.debug("hook with method %s is disabled, skipping",
                         hook.path)
            continue
        try:
            method = load_object_from_string(hook.path)
        except (AttributeError, ImportError):
            logger.exception("Unable to load method at %s:", hook.path)
            if required:
                raise
            continue
        try:
            result = method(context=context, provider=provider, **kwargs)
        except Exception:
            logger.exception("Method %s threw an exception:", hook.path)
            if required:
                raise
            continue
        if not result:
            if required:
                logger.error("Required hook %s failed. Return value: %s",
                             hook.path, result)
                sys.exit(1)
            logger.warning("Non-required hook %s failed. Return value: %s",
                           hook.path, result)
        else:
            if isinstance(result, collections.Mapping):
                if data_key:
                    logger.debug("Adding result for hook %s to context in "
                                 "data_key %s.", hook.path, data_key)
                    context.set_hook_data(data_key, result)
                else:
                    logger.debug("Hook %s returned result data, but no data "
                                 "key set, so ignoring.", hook.path)


def get_config_directory():
    """Return the directory the config file is located in.

    This enables us to use relative paths in config values.

    """
    # avoid circular import
    from .commands.stacker import Stacker
    command = Stacker()
    namespace = command.parse_args()
    return os.path.dirname(namespace.config.name)


def read_value_from_path(value):
    """Enables translators to read values from files.

    The value can be referred to with the `file://` prefix. ie:

        conf_key: ${kms file://kms_value.txt}

    """
    if value.startswith('file://'):
        path = value.split('file://', 1)[1]
        config_directory = get_config_directory()
        relative_path = os.path.join(config_directory, path)
        with open(relative_path) as read_file:
            value = read_file.read()
    return value


def get_client_region(client):
    """Gets the region from a :class:`boto3.client.Client` object.

    Args:
        client (:class:`boto3.client.Client`): The client to get the region
            from.

    Returns:
        string: AWS region string.
    """

    return client._client_config.region_name


def get_s3_endpoint(client):
    """Gets the s3 endpoint for the given :class:`boto3.client.Client` object.

    Args:
        client (:class:`boto3.client.Client`): The client to get the endpoint
            from.

    Returns:
        string: The AWS endpoint for the client.
    """

    return client._endpoint.host


def s3_bucket_location_constraint(region):
    """Returns the appropriate LocationConstraint info for a new S3 bucket.

    When creating a bucket in a region OTHER than us-east-1, you need to
    specify a LocationConstraint inside the CreateBucketConfiguration argument.
    This function helps you determine the right value given a given client.

    Args:
        region (str): The region where the bucket will be created in.

    Returns:
        string: The string to use with the given client for creating a bucket.
    """
    if region == "us-east-1":
        return ""
    return region


def ensure_s3_bucket(s3_client, bucket_name, bucket_region):
    """Ensure an s3 bucket exists, if it does not then create it.

    Args:
        s3_client (:class:`botocore.client.Client`): An s3 client used to
            verify and create the bucket.
        bucket_name (str): The bucket being checked/created.
        bucket_region (str, optional): The region to create the bucket in. If
            not provided, will be determined by s3_client's region.
    """
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == "Not Found":
            logger.debug("Creating bucket %s.", bucket_name)
            create_args = {"Bucket": bucket_name}
            location_constraint = s3_bucket_location_constraint(
                bucket_region
            )
            if location_constraint:
                create_args["CreateBucketConfiguration"] = {
                    "LocationConstraint": location_constraint
                }
            s3_client.create_bucket(**create_args)
        elif e.response['Error']['Message'] == "Forbidden":
            logger.exception("Access denied for bucket %s.  Did " +
                             "you remember to use a globally unique name?",
                             bucket_name)
            raise
        else:
            logger.exception("Error creating bucket %s. Error %s",
                             bucket_name, e.response)
            raise


def parse_cloudformation_template(template):
    """Parse CFN template string.

    Leverages the vendored aws-cli yamlhelper to handle JSON or YAML templates.

    Args:
        template (str): The template body.
    """
    return yaml_parse(template)


class Extractor(object):
    """Base class for extractors."""

    def __init__(self, archive=None):
        """
        Create extractor object with the archive path.

        Args:
            archive (string): Archive path
        """
        self.archive = archive

    def set_archive(self, dir_name):
        """
        Update archive filename to match directory name & extension.

        Args:
            dir_name (string): Archive directory name
        """
        self.archive = dir_name + self.extension()

    @staticmethod
    def extension():
        """Serve as placeholder; override this in subclasses."""
        return ''


class TarExtractor(Extractor):
    """Extracts tar archives."""

    def extract(self, destination):
        """Extract the archive."""
        with tarfile.open(self.archive, 'r:') as tar:
            tar.extractall(path=destination)

    @staticmethod
    def extension():
        """Return archive extension."""
        return '.tar'


class TarGzipExtractor(Extractor):
    """Extracts compressed tar archives."""

    def extract(self, destination):
        """Extract the archive."""
        with tarfile.open(self.archive, 'r:gz') as tar:
            tar.extractall(path=destination)

    @staticmethod
    def extension():
        """Return archive extension."""
        return '.tar.gz'


class ZipExtractor(Extractor):
    """Extracts zip archives."""

    def extract(self, destination):
        """Extract the archive."""
        with zipfile.ZipFile(self.archive, 'r') as zip_ref:
            zip_ref.extractall(destination)

    @staticmethod
    def extension():
        """Return archive extension."""
        return '.zip'


class SourceProcessor(object):
    """Makes remote python package sources available in current environment."""

    ISO8601_FORMAT = '%Y%m%dT%H%M%SZ'

    def __init__(self, sources, stacker_cache_dir=None):
        """
        Process a config's defined package sources.

        Args:
            sources (dict): Package sources from Stacker config dictionary
            stacker_cache_dir (string): Path where remote sources will be
                cached.
        """
        if not stacker_cache_dir:
            stacker_cache_dir = os.path.expanduser("~/.stacker")
        package_cache_dir = os.path.join(stacker_cache_dir, 'packages')
        self.stacker_cache_dir = stacker_cache_dir
        self.package_cache_dir = package_cache_dir
        self.sources = sources
        self.configs_to_merge = []
        self.create_cache_directories()

    def create_cache_directories(self):
        """Ensure that SourceProcessor cache directories exist."""
        if not os.path.isdir(self.package_cache_dir):
            if not os.path.isdir(self.stacker_cache_dir):
                os.mkdir(self.stacker_cache_dir)
            os.mkdir(self.package_cache_dir)

    def get_package_sources(self):
        """Make remote python packages available for local use."""
        # Checkout local modules
        for config in self.sources.get('local', []):
            self.fetch_local_package(config=config)
        # Checkout S3 repositories specified in config
        for config in self.sources.get('s3', []):
            self.fetch_s3_package(config=config)
        # Checkout git repositories specified in config
        for config in self.sources.get('git', []):
            self.fetch_git_package(config=config)

    def fetch_local_package(self, config):
        """Make a local path available to current stacker config.

        Args:
            config (dict): 'local' path config dictionary

        """
        # Update sys.path & merge in remote configs (if necessary)
        self.update_paths_and_config(config=config,
                                     pkg_dir_name=config['source'],
                                     pkg_cache_dir=os.getcwd())

    def fetch_s3_package(self, config):
        """Make a remote S3 archive available for local use.

        Args:
            config (dict): git config dictionary

        """
        extractor_map = {'.tar.gz': TarGzipExtractor,
                         '.tar': TarExtractor,
                         '.zip': ZipExtractor}
        extractor = None
        for suffix, klass in extractor_map.items():
            if config['key'].endswith(suffix):
                extractor = klass()
                logger.debug("Using extractor %s for S3 object \"%s\" in "
                             "bucket %s.",
                             klass.__name__,
                             config['key'],
                             config['bucket'])
                dir_name = self.sanitize_uri_path(
                    "s3-%s-%s" % (config['bucket'],
                                  config['key'][:-len(suffix)])
                )
                break

        if extractor is None:
            raise ValueError(
                "Archive type could not be determined for S3 object \"%s\" "
                "in bucket %s." % (config['key'], config['bucket'])
            )

        session = get_session(region=None)
        extra_s3_args = {}
        if config.get('requester_pays', False):
            extra_s3_args['RequestPayer'] = 'requester'

        # We can skip downloading the archive if it's already been cached
        if config.get('use_latest', True):
            try:
                # LastModified should always be returned in UTC, but it doesn't
                # hurt to explicitly convert it to UTC again just in case
                modified_date = session.client('s3').head_object(
                    Bucket=config['bucket'],
                    Key=config['key'],
                    **extra_s3_args
                )['LastModified'].astimezone(dateutil.tz.tzutc())
            except botocore.exceptions.ClientError as client_error:
                logger.error("Error checking modified date of "
                             "s3://%s/%s : %s",
                             config['bucket'],
                             config['key'],
                             client_error)
                sys.exit(1)
            dir_name += "-%s" % modified_date.strftime(self.ISO8601_FORMAT)
        cached_dir_path = os.path.join(self.package_cache_dir, dir_name)
        if not os.path.isdir(cached_dir_path):
            logger.debug("Remote package s3://%s/%s does not appear to have "
                         "been previously downloaded - starting download and "
                         "extraction to %s",
                         config['bucket'],
                         config['key'],
                         cached_dir_path)
            tmp_dir = tempfile.mkdtemp(prefix='stacker')
            tmp_package_path = os.path.join(tmp_dir, dir_name)
            try:
                extractor.set_archive(os.path.join(tmp_dir, dir_name))
                logger.debug("Starting remote package download from S3 to %s "
                             "with extra S3 options \"%s\"",
                             extractor.archive,
                             str(extra_s3_args))
                session.resource('s3').Bucket(config['bucket']).download_file(
                    config['key'],
                    extractor.archive,
                    ExtraArgs=extra_s3_args
                )
                logger.debug("Download complete; extracting downloaded "
                             "package to %s",
                             tmp_package_path)
                extractor.extract(tmp_package_path)
                logger.debug("Moving extracted package directory %s to the "
                             "Stacker cache at %s",
                             dir_name,
                             self.package_cache_dir)
                shutil.move(tmp_package_path, self.package_cache_dir)
            finally:
                shutil.rmtree(tmp_dir)
        else:
            logger.debug("Remote package s3://%s/%s appears to have "
                         "been previously downloaded to %s -- bypassing "
                         "download",
                         config['bucket'],
                         config['key'],
                         cached_dir_path)

        # Update sys.path & merge in remote configs (if necessary)
        self.update_paths_and_config(config=config,
                                     pkg_dir_name=dir_name)

    def fetch_git_package(self, config):
        """Make a remote git repository available for local use.

        Args:
            config (dict): git config dictionary

        """
        # only loading git here when needed to avoid load errors on systems
        # without git installed
        from git import Repo

        ref = self.determine_git_ref(config)
        dir_name = self.sanitize_git_path(uri=config['uri'], ref=ref)
        cached_dir_path = os.path.join(self.package_cache_dir, dir_name)

        # We can skip cloning the repo if it's already been cached
        if not os.path.isdir(cached_dir_path):
            logger.debug("Remote repo %s does not appear to have been "
                         "previously downloaded - starting clone to %s",
                         config['uri'],
                         cached_dir_path)
            tmp_dir = tempfile.mkdtemp(prefix='stacker')
            try:
                tmp_repo_path = os.path.join(tmp_dir, dir_name)
                with Repo.clone_from(config['uri'], tmp_repo_path) as repo:
                    repo.head.reference = ref
                    repo.head.reset(index=True, working_tree=True)
                shutil.move(tmp_repo_path, self.package_cache_dir)
            finally:
                shutil.rmtree(tmp_dir)
        else:
            logger.debug("Remote repo %s appears to have been previously "
                         "cloned to %s -- bypassing download",
                         config['uri'],
                         cached_dir_path)

        # Update sys.path & merge in remote configs (if necessary)
        self.update_paths_and_config(config=config,
                                     pkg_dir_name=dir_name)

    def update_paths_and_config(self, config, pkg_dir_name,
                                pkg_cache_dir=None):
        """Handle remote source defined sys.paths & configs.

        Args:
            config (dict): git config dictionary
            pkg_dir_name (string): directory name of the stacker archive
            pkg_cache_dir (string): fully qualified path to stacker cache
                                    cache directory

        """
        if pkg_cache_dir is None:
            pkg_cache_dir = self.package_cache_dir
        cached_dir_path = os.path.join(pkg_cache_dir, pkg_dir_name)

        # Add the appropriate directory (or directories) to sys.path
        if config.get('paths'):
            for path in config['paths']:
                path_to_append = os.path.join(cached_dir_path,
                                              path)
                logger.debug("Appending \"%s\" to python sys.path",
                             path_to_append)
                sys.path.append(path_to_append)
        else:
            sys.path.append(cached_dir_path)

        # If the configuration defines a set of remote config yamls to
        # include, add them to the list for merging
        if config.get('configs'):
            for config_filename in config['configs']:
                self.configs_to_merge.append(os.path.join(cached_dir_path,
                                                          config_filename))

    def git_ls_remote(self, uri, ref):
        """Determine the latest commit id for a given ref.

        Args:
            uri (string): git URI
            ref (string): git ref

        Returns:
            str: A commit id

        """
        logger.debug("Invoking git to retrieve commit id for repo %s...", uri)
        lsremote_output = subprocess.check_output(['git',
                                                   'ls-remote',
                                                   uri,
                                                   ref])
        if b"\t" in lsremote_output:
            commit_id = lsremote_output.split(b"\t")[0]
            logger.debug("Matching commit id found: %s", commit_id)
            return commit_id
        else:
            raise ValueError("Ref \"%s\" not found for repo %s." % (ref, uri))

    def determine_git_ls_remote_ref(self, config):
        """Determine the ref to be used with the "git ls-remote" command.

        Args:
            config (:class:`stacker.config.GitPackageSource`): git config
                dictionary; 'branch' key is optional

        Returns:
            str: A branch reference or "HEAD"

        """
        if config.get('branch'):
            ref = "refs/heads/%s" % config['branch']
        else:
            ref = "HEAD"

        return ref

    def determine_git_ref(self, config):
        """Determine the ref to be used for 'git checkout'.

        Args:
            config (dict): git config dictionary

        Returns:
            str: A commit id or tag name

        """
        # First ensure redundant config keys aren't specified (which could
        # cause confusion as to which take precedence)
        ref_config_keys = 0
        for i in ['commit', 'tag', 'branch']:
            if config.get(i):
                ref_config_keys += 1
        if ref_config_keys > 1:
            raise ImportError("Fetching remote git sources failed: "
                              "conflicting revisions (e.g. 'commit', 'tag', "
                              "'branch') specified for a package source")

        # Now check for a specific point in time referenced and return it if
        # present
        if config.get('commit'):
            ref = config['commit']
        elif config.get('tag'):
            ref = config['tag']
        else:
            # Since a specific commit/tag point in time has not been specified,
            # check the remote repo for the commit id to use
            ref = self.git_ls_remote(
                config['uri'],
                self.determine_git_ls_remote_ref(config)
            )
        if sys.version_info[0] > 2 and isinstance(ref, bytes):
            return ref.decode()
        return ref

    def sanitize_uri_path(self, uri):
        """Take a URI and converts it to a directory safe path.

        Args:
            uri (string): URI (e.g. http://example.com/cats)

        Returns:
            str: Directory name for the supplied uri

        """
        for i in ['@', '/', ':']:
            uri = uri.replace(i, '_')
        return uri

    def sanitize_git_path(self, uri, ref=None):
        """Take a git URI and ref and converts it to a directory safe path.

        Args:
            uri (string): git URI
                          (e.g. git@github.com:foo/bar.git)
            ref (string): optional git ref to be appended to the path

        Returns:
            str: Directory name for the supplied uri

        """
        if uri.endswith('.git'):
            dir_name = uri[:-4]  # drop .git
        else:
            dir_name = uri
        dir_name = self.sanitize_uri_path(dir_name)
        if ref is not None:
            dir_name += "-%s" % ref
        return dir_name


def stack_template_key_name(blueprint):
    """Given a blueprint, produce an appropriate key name.

    Args:
        blueprint (:class:`stacker.blueprints.base.Blueprint`): The blueprint
            object to create the key from.

    Returns:
        string: Key name resulting from blueprint.
    """
    name = blueprint.name
    return "stack_templates/%s/%s-%s.json" % (blueprint.context.get_fqn(name),
                                              name,
                                              blueprint.version)
