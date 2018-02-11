import copy
import sys
import logging

from string import Template
from StringIO import StringIO

from schematics import Model
from schematics.exceptions import ValidationError
from schematics.exceptions import BaseError as SchematicsError
from schematics.types import (
    ModelType,
    ListType,
    StringType,
    BooleanType,
    DictType,
    BaseType
)

import yaml

from ..lookups import register_lookup_handler
from ..util import merge_map, yaml_to_ordered_dict, SourceProcessor
from .. import exceptions

# register translators (yaml constructors)
from .translators import *  # NOQA

logger = logging.getLogger(__name__)


def render_parse_load(raw_config, environment=None, validate=True):
    """Encapsulates the render -> parse -> validate -> load process.

    Args:
        raw_config (str): the raw stacker configuration string.
        environment (dict, optional): any environment values that should be
            passed to the config
        validate (bool): if provided, the config is validated before being
            loaded.

    Returns:
        :class:`Config`: the parsed stacker config.

    """

    pre_rendered = render(raw_config, environment)

    rendered = process_remote_sources(pre_rendered, environment)

    config = parse(rendered)

    # For backwards compatibility, if the config doesn't specify a namespace,
    # we fall back to fetching it from the environment, if provided.
    if config.namespace is None:
        namespace = environment.get("namespace")
        if namespace:
            logger.warn("DEPRECATION WARNING: specifying namespace in the "
                        "environment is deprecated. See "
                        "https://stacker.readthedocs.io/en/latest/config.html"
                        "#namespace "
                        "for more info.")
            config.namespace = namespace

    if validate:
        config.validate()

    return load(config)


def render(raw_config, environment=None):
    """Renders a config, using it as a template with the environment.

    Args:
        raw_config (str): the raw stacker configuration string.
        environment (dict, optional): any environment values that should be
            passed to the config

    Returns:
        str: the stacker configuration populated with any values passed from
            the environment

    """

    t = Template(raw_config)
    buff = StringIO()
    if not environment:
        environment = {}
    try:
        buff.write(t.substitute(environment))
    except KeyError, e:
        raise exceptions.MissingEnvironment(e.args[0])
    except ValueError:
        # Support "invalid" placeholders for lookup placeholders.
        buff.write(t.safe_substitute(environment))

    buff.seek(0)
    return buff.read()


def parse(raw_config):
    """Parse a raw yaml formatted stacker config.

    Args:
        raw_config (str): the raw stacker configuration string in yaml format.

    Returns:
        :class:`Config`: the parsed stacker config.

    """

    # Convert any applicable dictionaries back into lists
    # This is necessary due to the move from lists for these top level config
    # values to either lists or OrderedDicts.
    # Eventually we should probably just make them OrderedDicts only.
    config_dict = yaml_to_ordered_dict(raw_config)
    if config_dict:
        for top_level_key in ['stacks', 'pre_build', 'post_build',
                              'pre_destroy', 'post_destroy']:
            top_level_value = config_dict.get(top_level_key)
            if isinstance(top_level_value, dict):
                tmp_list = []
                for key, value in top_level_value.iteritems():
                    tmp_dict = copy.deepcopy(value)
                    if top_level_key == 'stacks':
                        tmp_dict['name'] = key
                    tmp_list.append(tmp_dict)
                config_dict[top_level_key] = tmp_list

    # We have to enable non-strict mode, because people may be including top
    # level keys for re-use with stacks (e.g. including something like
    # `common_variables: &common_variables`).
    #
    # The unfortunate side effect of this is that it propagates down to every
    # schematics model, and there doesn't seem to be a good way to only disable
    # strict mode on a single model.
    #
    # If we enabled strict mode, it would break backwards compatibility, so we
    # should consider enabling this in the future.
    strict = False

    return Config(config_dict, strict=strict)


def load(config):
    """Loads a stacker configuration by modifying sys paths, loading lookups,
    etc.

    Args:
        config (:class:`Config`): the stacker config to load.

    Returns:
        :class:`Config`: the stacker config provided above.

    """

    if config.sys_path:
        logger.debug("Appending %s to sys.path.", config.sys_path)
        sys.path.append(config.sys_path)
        logger.debug("sys.path is now %s", sys.path)
    if config.lookups:
        for key, handler in config.lookups.iteritems():
            register_lookup_handler(key, handler)

    return config


def dump(config):
    """Dumps a stacker Config object as yaml.

    Args:
        config (:class:`Config`): the stacker Config object.
        stream (stream): an optional stream object to write to.

    Returns:
        str: the yaml formatted stacker Config.

    """

    return yaml.safe_dump(
        config.to_primitive(),
        default_flow_style=False,
        encoding='utf-8',
        allow_unicode=True)


def process_remote_sources(raw_config, environment=None):
    """Stage remote package sources and merge in remote configs.

    Args:
        raw_config (str): the raw stacker configuration string.
        environment (dict, optional): any environment values that should be
            passed to the config

    Returns:
        str: the raw stacker configuration string

    """

    config = yaml.safe_load(raw_config)
    if config and config.get('package_sources'):
        processor = SourceProcessor(
            sources=config['package_sources'],
            stacker_cache_dir=config.get('stacker_cache_dir')
        )
        processor.get_package_sources()
        if processor.configs_to_merge:
            for i in processor.configs_to_merge:
                logger.debug("Merging in remote config \"%s\"", i)
                remote_config = yaml.safe_load(open(i))
                config = merge_map(remote_config, config)
            # Call the render again as the package_sources may have merged in
            # additional environment lookups
            if not environment:
                environment = {}
            return render(str(config), environment)

    return raw_config


def not_empty_list(value):
    if not value or len(value) < 1:
        raise ValidationError("Should have more than one element.")
    return value


class AnyType(BaseType):
    pass


class GitPackageSource(Model):
    uri = StringType(required=True)

    tag = StringType(serialize_when_none=False)

    branch = StringType(serialize_when_none=False)

    commit = StringType(serialize_when_none=False)

    paths = ListType(StringType, serialize_when_none=False)

    configs = ListType(StringType, serialize_when_none=False)


class S3PackageSource(Model):
    bucket = StringType(required=True)

    key = StringType(required=True)

    use_latest = BooleanType(serialize_when_none=False)

    requester_pays = BooleanType(serialize_when_none=False)


class PackageSources(Model):
    git = ListType(ModelType(GitPackageSource))

    s3 = ListType(ModelType(S3PackageSource))


class Hook(Model):
    path = StringType(required=True)

    required = BooleanType(default=True)

    data_key = StringType(serialize_when_none=False)

    args = DictType(AnyType)


class Stack(Model):
    name = StringType(required=True)

    class_path = StringType(serialize_when_none=False)

    template_path = StringType(serialize_when_none=False)

    description = StringType(serialize_when_none=False)

    requires = ListType(StringType, serialize_when_none=False)

    locked = BooleanType(default=False)

    enabled = BooleanType(default=True)

    protected = BooleanType(default=False)

    variables = DictType(AnyType, serialize_when_none=False)

    parameters = DictType(AnyType, serialize_when_none=False)

    tags = DictType(StringType, serialize_when_none=False)

    def validate_class_path(self, data, value):
        if value and data["template_path"]:
            raise ValidationError(
                "template_path cannot be present when "
                "class_path is provided.")
        self.validate_stack_source(data)

    def validate_template_path(self, data, value):
        if value and data["class_path"]:
            raise ValidationError(
                "class_path cannot be present when "
                "template_path is provided.")
        self.validate_stack_source(data)

    def validate_stack_source(self, data):
        if not (data["class_path"] or data["template_path"]):
            raise ValidationError(
                "class_path or template_path is required.")

    def validate_parameters(self, data, value):
        if value:
            stack_name = data['name']
            raise ValidationError(
                    "DEPRECATION: Stack definition %s contains "
                    "deprecated 'parameters', rather than 'variables'. You are"
                    " required to update your config. See https://stacker.rea"
                    "dthedocs.io/en/latest/config.html#variables for "
                    "additional information."
                    % stack_name)
        return value


class Config(Model):
    """This is the Python representation of a stacker config file.

    This is used internally by stacker to parse and validate a yaml formatted
    stacker configuration file, but can also be used in scripts to generate a
    stacker config file before handing it off to stacker to build/destroy.

    Example::

        from stacker.config import dump, Config, Stack

        vpc = Stack({
            "name": "vpc",
            "class_path": "blueprints.VPC"})

        config = Config()
        config.namespace = "prod"
        config.stacks = [vpc]

        print dump(config)

    """

    namespace = StringType(required=True)

    namespace_delimiter = StringType(serialize_when_none=False)

    stacker_bucket = StringType(serialize_when_none=False)

    stacker_bucket_region = StringType(serialize_when_none=False)

    stacker_cache_dir = StringType(serialize_when_none=False)

    sys_path = StringType(serialize_when_none=False)

    package_sources = ModelType(PackageSources, serialize_when_none=False)

    service_role = StringType(serialize_when_none=False)

    pre_build = ListType(ModelType(Hook), serialize_when_none=False)

    post_build = ListType(ModelType(Hook), serialize_when_none=False)

    pre_destroy = ListType(ModelType(Hook), serialize_when_none=False)

    post_destroy = ListType(ModelType(Hook), serialize_when_none=False)

    tags = DictType(StringType, serialize_when_none=False)

    template_indent = StringType(serialize_when_none=False)

    mappings = DictType(
        DictType(DictType(StringType)), serialize_when_none=False)

    lookups = DictType(StringType, serialize_when_none=False)

    stacks = ListType(
        ModelType(Stack), default=[], validators=[not_empty_list])

    def validate(self):
        try:
            super(Config, self).validate()
        except SchematicsError as e:
            raise exceptions.InvalidConfig(e.errors)

    def validate_stacks(self, data, value):
        if value:
            stack_names = [stack.name for stack in value]
            if len(set(stack_names)) != len(stack_names):
                # only loop / enumerate if there is an issue.
                for i, stack_name in enumerate(stack_names):
                    if stack_names.count(stack_name) != 1:
                        raise ValidationError(
                            "Duplicate stack %s found at index %d."
                            % (stack_name, i))
