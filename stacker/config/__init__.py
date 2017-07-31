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
from ..util import SourceProcessor
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

    rendered = render(raw_config, environment)

    # Stage any remote package sources and merge into their defined
    # configurations (if any)
    pre_config = yaml.safe_load(rendered)
    if pre_config.get('package_sources'):
        processor = SourceProcessor(config=pre_config)
        processor.get_package_sources()
        # Call the render again as the package_sources may have merged in
        # additional environment lookups
        rendered = render(str(processor.config), environment)

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
    config_dict = yaml.safe_load(raw_config)
    if config_dict.get('stacks') and isinstance(config_dict['stacks'], dict):
        stack_list = []
        for key, value in config_dict['stacks'].iteritems():
            tmp_dict = value
            tmp_dict['name'] = key
            stack_list.append(tmp_dict)
        config_dict['stacks'] = stack_list
    for stage in ['pre', 'post']:
        for i in ['%s_build' % stage, '%s_destroy' % stage]:
            if config_dict.get(i) and isinstance(config_dict[i], dict):
                hook_list = []
                for key, value in config_dict[i].iteritems():
                    tmp_dict = value
                    hook_list.append(tmp_dict)
                config_dict[i] = hook_list

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


class PackageSources(Model):
    git = ListType(ModelType(GitPackageSource))


class Hook(Model):
    path = StringType(required=True)

    required = BooleanType(default=True)

    data_key = StringType(serialize_when_none=False)

    args = DictType(AnyType)


class Stack(Model):
    name = StringType(required=True)

    class_path = StringType(required=True)

    requires = ListType(StringType, serialize_when_none=False)

    locked = BooleanType(default=False)

    enabled = BooleanType(default=True)

    protected = BooleanType(default=False)

    variables = DictType(AnyType, serialize_when_none=False)

    parameters = DictType(AnyType, serialize_when_none=False)

    tags = DictType(StringType, serialize_when_none=False)

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

    pre_build = ListType(ModelType(Hook), serialize_when_none=False)

    post_build = ListType(ModelType(Hook), serialize_when_none=False)

    pre_destroy = ListType(ModelType(Hook), serialize_when_none=False)

    post_destroy = ListType(ModelType(Hook), serialize_when_none=False)

    tags = DictType(StringType, serialize_when_none=False)

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
            names = set()
            for i, stack in enumerate(value):
                if stack.name in names:
                    raise ValidationError(
                        "Duplicate stack %s found at index %d."
                        % (stack.name, i))
                names.add(stack.name)
