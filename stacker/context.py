import collections
import logging

from stacker.config import Config
from .stack import Stack

logger = logging.getLogger(__name__)


DEFAULT_NAMESPACE_DELIMITER = "-"
DEFAULT_TEMPLATE_INDENT = 4


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
        config (:class:`stacker.config.Config`): The stacker configuration
            being operated on.
        force_stacks (list): A list of stacks to force work on. Used to work
            on locked stacks.

    """

    def __init__(self, environment=None,
                 stack_names=None,
                 config=None,
                 force_stacks=None):
        self.environment = environment
        self.stack_names = stack_names or []
        self.config = config or Config()
        self.force_stacks = force_stacks or []
        self.hook_data = {}

    @property
    def namespace(self):
        return self.config.namespace

    @property
    def namespace_delimiter(self):
        delimiter = self.config.namespace_delimiter
        if delimiter is not None:
            return delimiter
        return DEFAULT_NAMESPACE_DELIMITER

    @property
    def template_indent(self):
        indent = self.config.template_indent
        if indent is not None:
            return int(indent)
        return DEFAULT_TEMPLATE_INDENT

    @property
    def bucket_name(self):
        if not self.upload_templates_to_s3:
            return None

        return self.config.stacker_bucket \
            or "stacker-%s" % (self.get_fqn(),)

    @property
    def upload_templates_to_s3(self):
        # Don't upload stack templates to S3 if `stacker_bucket` is explicitly
        # set to an empty string.
        if self.config.stacker_bucket == '':
            logger.debug("Not uploading templates to s3 because "
                         "`stacker_bucket` is explicity set to an "
                         "empty string")
            return False

        # If no namespace is specificied, and there's no explicit stacker
        # bucket specified, don't upload to s3. This makes sense because we
        # can't realistically auto generate a stacker bucket name in this case.
        if not self.namespace and not self.config.stacker_bucket:
            logger.debug("Not uploading templates to s3 because "
                         "there is no namespace set, and no "
                         "stacker_bucket set")
            return False

        return True

    @property
    def tags(self):
        tags = self.config.tags
        if tags is not None:
            return tags
        if self.namespace:
            return {"stacker_namespace": self.namespace}
        return {}

    @property
    def _base_fqn(self):
        return self.namespace.replace(".", "-").lower()

    @property
    def mappings(self):
        return self.config.mappings or {}

    def _get_stack_definitions(self):
        return self.config.stacks

    def get_stacks(self):
        """Get the stacks for the current action.

        Handles configuring the :class:`stacker.stack.Stack` objects that will
        be used in the current action.

        Returns:
            list: a list of :class:`stacker.stack.Stack` objects

        """
        if not hasattr(self, "_stacks"):
            stacks = []
            definitions = self._get_stack_definitions()
            for stack_def in definitions:
                stack = Stack(
                    definition=stack_def,
                    context=self,
                    mappings=self.mappings,
                    force=stack_def.name in self.force_stacks,
                    locked=stack_def.locked,
                    enabled=stack_def.enabled,
                    protected=stack_def.protected,
                )
                stacks.append(stack)
            self._stacks = stacks
        return self._stacks

    def get_stack(self, name):
        for stack in self.get_stacks():
            if stack.name == name:
                return stack

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
