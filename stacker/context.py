import collections
import logging
import sys

from stacker.util import SourceProcessor
from .exceptions import MissingConfig
from .config import parse_config
from .stack import Stack
from .lookups import register_lookup_handler

logger = logging.getLogger(__name__)


DEFAULT_NAMESPACE_DELIMITER = "-"


def get_fqn(base_fqn, delimiter, name=None):
    """Return the fully qualified name of an object within this context.

    If the name passed already appears to be a fully qualified name, it
    will be returned with no further processing.

    """
    if name and name.startswith("%s%s" % (base_fqn, delimiter)):
        return name

    return delimiter.join(filter(None, [base_fqn, name]))


class Context(object):
    """The context under which the current stacks are being executed.

    The stacker Context is responsible for translating the values passed in via
    the command line and specified in the config to `Stack` objects.

    Args:
        environment (dict): A dictionary used to pass in information about
            the environment. Useful for templating.
        stack_names (list): A list of stack_names to operate on. If not passed,
            usually all stacks defined in the config will be operated on.
        config (dict): The configuration being operated on, containing the
            stack definitions.
        force_stacks (list): A list of stacks to force work on. Used to work
            on locked stacks.

    """

    def __init__(self, environment=None,
                 stack_names=None,
                 config=None,
                 logger_type=None,
                 force_stacks=None):
        self.environment = environment
        self.stack_names = stack_names or []
        self.logger_type = logger_type
        self.config = config or {}
        self.force_stacks = force_stacks or []
        self.hook_data = {}

    @property
    def namespace(self):
        namespace = self.config.get("namespace")
        if namespace is not None:
            return namespace

        # For backwards compatibility, we fallback to attempting to
        # fetch the namespace from the environment file, if provided.
        namespace = self.environment.get("namespace")
        if namespace:
            logger.warn("specifying namespace in the environment is "
                        "deprecated, and should be moved to the config")
            return namespace

        # Raise an error if no namespace was provided.
        raise MissingConfig("namespace")

    @property
    def namespace_delimiter(self):
        return self.config.get(
                "namespace_delimiter",
                DEFAULT_NAMESPACE_DELIMITER)

    @property
    def bucket_name(self):
        return self.config.get("stacker_bucket") \
                or "stacker-%s" % (self.get_fqn(),)

    @property
    def tags(self):
        tags = self.config.get("tags", None)
        if tags is not None:
            return dict([(str(tag_key), str(tag_value)) for tag_key,
                         tag_value in tags.items()])
        else:
            return {'stacker_namespace': self.namespace}

    @property
    def _base_fqn(self):
        return self.namespace.replace(".", "-").lower()

    @property
    def mappings(self):
        return self.config.get("mappings", {})

    def load_config(self, conf_string):
        self.config = parse_config(conf_string, environment=self.environment)
        if "sys_path" in self.config:
            logger.debug("Appending %s to sys.path.", self.config["sys_path"])
            sys.path.append(self.config["sys_path"])
            logger.debug("sys.path is now %s", sys.path)
        lookups = self.config.get("lookups", {})
        for key, handler in lookups.iteritems():
            register_lookup_handler(key, handler)
        sources = self.config.get("package_sources")
        if sources is not None:
            processor = SourceProcessor(
                stacker_cache_dir=self.config.get("stacker_cache_dir")
            )
            processor.get_package_sources(sources=sources)

    def _get_stack_definitions(self):
        if not self.stack_names:
            return self.config["stacks"]
        return [s for s in self.config["stacks"] if s["name"] in
                self.stack_names]

    def get_stacks(self):
        """Get the stacks for the current action.

        Handles configuring the :class:`stacker.stack.Stack` objects that will
        be used in the current action.

        Returns:
            list: a list of :class:`stacker.stack.Stack` objects

        """
        stacks = []
        definitions = self._get_stack_definitions()
        for stack_def in definitions:
            stack = Stack(
                definition=stack_def,
                context=self,
                mappings=self.mappings,
                force=stack_def["name"] in self.force_stacks,
                locked=stack_def.get("locked", False),
                enabled=stack_def.get("enabled", True),
            )
            stacks.append(stack)
        return stacks

    def get_stacks_dict(self):
        return dict((stack.fqn, stack) for stack in self.get_stacks())

    def get_fqn(self, name=None):
        """Return the fully qualified name of an object within this context.

        If the name passed already appears to be a fully qualified name, it
        will be returned with no further processing.

        """
        return get_fqn(self._base_fqn, self.namespace_delimiter, name)

    def set_hook_data(self, key, data):
        """Set hook data for the given key.

        Args:
            key(str): The key to store the hook data in.
            data(:class:`collections.Mapping`): A dictionary of data to store,
                as returned from a hook.
        """

        if not isinstance(data, collections.Mapping):
            raise ValueError("Hook (key: %s) data must be an instance of "
                             "collections.Mapping (a dictionary for "
                             "example)." % key)

        if key in self.hook_data:
            raise KeyError("Hook data for key %s already exists, each hook "
                           "must have a unique data_key.", key)

        self.hook_data[key] = data
