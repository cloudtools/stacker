from past.types import basestring
import copy
import sys
import logging
import re

from string import Template
from io import StringIO

from schematics import Model
from schematics.exceptions import ValidationError
from schematics.exceptions import (
    BaseError as SchematicsError,
    UndefinedValueError
)

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
from ..environment import DictWithSourceType

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
        environment (DictWithSourceType, optional): any environment values that
            should be passed to the config

    Returns:
        str: the stacker configuration populated with any values passed from
            the environment

    """
    if not environment:
        environment = {}
    # If we have a naked dict, we got here through the old non-YAML path, so
    # we can't have a YAML config file.
    is_yaml = False
    if type(environment) == DictWithSourceType:
        is_yaml = environment.source_type == 'yaml'

    if is_yaml:
        # First, read the config as yaml
        config = yaml.safe_load(raw_config)

        # Next, we need to walk the yaml structure, and find all things which
        # look like variable references. This regular expression is copied from
        # string.template to match variable references identically as the
        # simple configuration case below. We've got two cases of this pattern,
        # since python 2.7 doesn't support re.fullmatch(), so we have to add
        # the end of line anchor to the inner patterns.
        idpattern = r'[_a-z][_a-z0-9]*'
        pattern = r"""
            %(delim)s(?:
              (?P<named>%(id)s)         |   # delimiter and a Python identifier
              {(?P<braced>%(id)s)}         # delimiter and a braced identifier
            )
            """ % {'delim': re.escape('$'),
                   'id': idpattern,
                   }
        full_pattern = r"""
            %(delim)s(?:
              (?P<named>%(id)s)$         |  # delimiter and a Python identifier
              {(?P<braced>%(id)s)}$         # delimiter and a braced identifier
            )
            """ % {'delim': re.escape('$'),
                   'id': idpattern,
                   }
        exp = re.compile(pattern, re.IGNORECASE | re.VERBOSE)
        full_exp = re.compile(full_pattern, re.IGNORECASE | re.VERBOSE)
        new_config = substitute_references(config, environment, exp, full_exp)
        # Now, re-encode the whole thing as YAML and return that.
        return yaml.safe_dump(new_config)
    else:
        t = Template(raw_config)
        buff = StringIO()

        try:
            substituted = t.substitute(environment)
        except KeyError as e:
            raise exceptions.MissingEnvironment(e.args[0])
        except ValueError:
            # Support "invalid" placeholders for lookup placeholders.
            substituted = t.safe_substitute(environment)

        if not isinstance(substituted, str):
            substituted = substituted.decode('utf-8')

        buff.write(substituted)
        buff.seek(0)
        return buff.read()


def substitute_references(root, environment, exp, full_exp):
    # We need to check for something being a string in both python 2.7 and
    # 3+. The aliases in the future package don't work for yaml sourced
    # strings, so we have to spin our own.
    def isstr(s):
        try:
            return isinstance(s, basestring)
        except NameError:
            return isinstance(s, str)

    if isinstance(root, list):
        result = []
        for x in root:
            result.append(substitute_references(x, environment, exp, full_exp))
        return result
    elif isinstance(root, dict):
        result = {}
        for k, v in root.items():
            result[k] = substitute_references(v, environment, exp, full_exp)
        return result
    elif isstr(root):
        # Strings are the special type where all substitutions happen. If we
        # encounter a string object in the expression tree, we need to perform
        # one of two different kinds of matches on it. First, if the entire
        # string is a variable, we can replace it with an arbitrary object;
        # dict, list, primitive. If the string contains variables within it,
        # then we have to do string substitution.
        match_obj = full_exp.match(root.strip())
        if match_obj:
            matches = match_obj.groupdict()
            var_name = matches['named'] or matches['braced']
            if var_name is not None:
                value = environment.get(var_name)
                if value is None:
                    raise exceptions.MissingEnvironment(var_name)
                return value

        # Returns if an object is a basic type. Once again, the future package
        # overrides don't work for string here, so we have to special case it
        def is_basic_type(o):
            if isstr(o):
                return True
            basic_types = [int, bool, float]
            for t in basic_types:
                if isinstance(o, t):
                    return True
            return False

        # If we got here, then we didn't have any full matches, now perform
        # partial substitutions within a string.
        def replace(mo):
            name = mo.groupdict()['braced'] or mo.groupdict()['named']
            if not name:
                return root[mo.start():mo.end()]
            val = environment.get(name)
            if val is None:
                raise exceptions.MissingEnvironment(name)
            if not is_basic_type(val):
                raise exceptions.WrongEnvironmentType(name)
            return str(val)
        value = exp.sub(replace, root)
        return value
    # In all other unhandled cases, return a copy of the input
    return copy.copy(root)


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
                for key, value in top_level_value.items():
                    tmp_dict = copy.deepcopy(value)
                    if top_level_key == 'stacks':
                        tmp_dict['name'] = key
                    tmp_list.append(tmp_dict)
                config_dict[top_level_key] = tmp_list

    # Top-level excess keys are removed by Config._convert, so enabling strict
    # mode is fine here.
    try:
        return Config(config_dict, strict=True)
    except SchematicsError as e:
        raise exceptions.InvalidConfig(e.errors)


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
        for key, handler in config.lookups.items():
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


class LocalPackageSource(Model):
    source = StringType(required=True)

    paths = ListType(StringType, serialize_when_none=False)

    configs = ListType(StringType, serialize_when_none=False)


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

    paths = ListType(StringType, serialize_when_none=False)

    configs = ListType(StringType, serialize_when_none=False)


class PackageSources(Model):
    local = ListType(ModelType(LocalPackageSource))

    git = ListType(ModelType(GitPackageSource))

    s3 = ListType(ModelType(S3PackageSource))


class Hook(Model):
    path = StringType(required=True)

    required = BooleanType(default=True)

    enabled = BooleanType(default=True)

    data_key = StringType(serialize_when_none=False)

    args = DictType(AnyType)


class Target(Model):
    name = StringType(required=True)

    requires = ListType(StringType, serialize_when_none=False)

    required_by = ListType(StringType, serialize_when_none=False)


class Stack(Model):
    name = StringType(required=True)

    stack_name = StringType(serialize_when_none=False)

    region = StringType(serialize_when_none=False)

    profile = StringType(serialize_when_none=False)

    class_path = StringType(serialize_when_none=False)

    template_path = StringType(serialize_when_none=False)

    description = StringType(serialize_when_none=False)

    requires = ListType(StringType, serialize_when_none=False)

    required_by = ListType(StringType, serialize_when_none=False)

    locked = BooleanType(default=False)

    enabled = BooleanType(default=True)

    protected = BooleanType(default=False)

    variables = DictType(AnyType, serialize_when_none=False)

    parameters = DictType(AnyType, serialize_when_none=False)

    tags = DictType(StringType, serialize_when_none=False)

    stack_policy_path = StringType(serialize_when_none=False)

    in_progress_behavior = StringType(serialize_when_none=False)

    notification_arns = ListType(
        StringType, serialize_when_none=False, default=[])

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
        # Locked stacks don't actually need a template, since they're
        # read-only.
        if data["locked"]:
            return

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

    targets = ListType(
        ModelType(Target), serialize_when_none=False)

    stacks = ListType(
        ModelType(Stack), default=[])

    log_formats = DictType(StringType, serialize_when_none=False)

    def _remove_excess_keys(self, data):
        excess_keys = set(data.keys())
        excess_keys -= self._schema.valid_input_keys
        if not excess_keys:
            return data

        logger.debug('Removing excess keys from config input: %s',
                     excess_keys)
        clean_data = data.copy()
        for key in excess_keys:
            del clean_data[key]

        return clean_data

    def _convert(self, raw_data=None, context=None, **kwargs):
        if raw_data is not None:
            # Remove excess top-level keys, since we want to allow them to be
            # used for custom user variables to be reference later. This is
            # preferable to just disabling strict mode, as we can still
            # disallow excess keys in the inner models.
            raw_data = self._remove_excess_keys(raw_data)

        return super(Config, self)._convert(raw_data=raw_data, context=context,
                                            **kwargs)

    def validate(self, *args, **kwargs):
        try:
            return super(Config, self).validate(*args, **kwargs)
        except UndefinedValueError as e:
            raise exceptions.InvalidConfig([e.message])
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
