import collections
import sys

from .config import parse_config
from .exceptions import MissingEnvironment
from .stack import Stack
from .lookups import register_lookup_handler


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
        namespace (str): A unique namespace for the stacks being built.
        environment (dict): A dictionary used to pass in information about
            the environment. Useful for templating.
        stack_names (list): A list of stack_names to operate on. If not passed,
            usually all stacks defined in the config will be operated on.
        mappings (dict): Used as Cloudformation mappings for the blueprint.
        config (dict): The configuration being operated on, containing the
            stack definitions.
        force_stacks (list): A list of stacks to force work on. Used to work
            on locked stacks.

    """

    def __init__(self, environment,  # pylint: disable-msg=too-many-arguments
                 stack_names=None,
                 mappings=None,
                 config=None,
                 logger_type=None,
                 force_stacks=None):
        try:
            self.namespace = environment["namespace"]
        except KeyError:
            raise MissingEnvironment(["namespace"])

        self.environment = environment
        self.stack_names = stack_names or []
        self.mappings = mappings or {}
        self.logger_type = logger_type
        self.namespace_delimiter = "-"
        self.config = config or {}
        self.force_stacks = force_stacks or []
        self._base_fqn = self.namespace.replace(".", "-").lower()
        self.bucket_name = "stacker-%s" % (self.get_fqn(),)
        self.tags = {
            'stacker_namespace': self.namespace
        }

        self.hook_data = {}

    def load_config(self, conf_string):
        self.config = parse_config(conf_string, environment=self.environment)
        self.mappings = self.config.get("mappings", {})
        namespace_delimiter = self.config.get("namespace_delimiter", None)
        if "sys_path" in self.config:
            sys.path.append(self.config["sys_path"])
        if namespace_delimiter is not None:
            self.namespace_delimiter = namespace_delimiter
        bucket_name = self.config.get("stacker_bucket", None)
        if bucket_name:
            self.bucket_name = bucket_name
        tags = self.config.get("tags", None)
        if tags is not None:
            self.tags = dict([(str(tag_key), str(tag_value)) for tag_key,
                              tag_value in tags.items()])
        lookups = self.config.get("lookups", {})
        for key, handler in lookups.iteritems():
            register_lookup_handler(key, handler)

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
