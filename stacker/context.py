from .exceptions import MissingEnvironment
from .config import parse_config
from .stack import Stack


def get_fqn(base_fqn, name=None):
    """Return the fully qualified name of an object within this context.

    If the name passed already appears to be a fully qualified name, it
    will be returned with no further processing.

    """
    if name and name.startswith(base_fqn + '-'):
        return name

    return '-'.join(filter(None, [base_fqn, name]))


class Context(object):
    """The context under which the current stacks are being executed.

    The stacker Context is responsible for translating the values passed in via
    the command line and specified in the config to `Stack` objects.

    Args:
        namespace (string): A unique namespace for the stacks being built.
        environment (dict): A dictionary used to pass in information about
            the environment. Useful for templating.
        stack_names (list): A list of stack_names to operate on. If not passed,
            usually all stacks defined in the config will be operated on.
        parameters (dict): Parameters passed down to each blueprint to
            parameterize the templates.
        mappings (dict): Used as Cloudformation mappings for the blueprint.
        config (dict): The configuration being operated on, containing the
            stack definitions.
        force_stacks (list): A list of stacks to force work on. Used to work
            on locked stacks.

    """

    def __init__(self, environment, stack_names=None,
                 parameters=None, mappings=None, config=None,
                 force_stacks=None):
        try:
            self.namespace = environment['namespace']
        except KeyError:
            raise MissingEnvironment(['namespace'])

        self.environment = environment
        self.stack_names = stack_names or []
        self.parameters = parameters or {}
        self.mappings = mappings or {}
        self.config = config or {}
        self.force_stacks = force_stacks or []
        self._base_fqn = self.namespace.replace('.', '-').lower()
        self.bucket_name = 'stacker-%s' % (self.get_fqn(),)

    def load_config(self, conf_string):
        self.config = parse_config(conf_string, environment=self.environment)
        self.mappings = self.config.get('mappings', {})
        bucket_name = self.config.get('stacker_bucket', None)
        if bucket_name:
            self.bucket_name = bucket_name

    def _get_stack_definitions(self):
        if not self.stack_names:
            return self.config['stacks']
        return [s for s in self.config['stacks'] if s['name'] in
                self.stack_names]

    def get_stacks(self):
        """Get the stacks for the current action.

        Handles configuring the `stacker.stack.Stack` objects that will be used
        in the current action. Responsible for merging the stack definition in
        the config, the parameters specified on the command line, and any
        mappings specified in the config.

        Returns:
            list: a list of :class:`stacker.stack.Stack` objects

        """
        stacks = []
        definitions = self._get_stack_definitions()
        for stack_def in definitions:
            stack = Stack(
                definition=stack_def,
                context=self,
                parameters=self.parameters,
                mappings=self.mappings,
                force=stack_def['name'] in self.force_stacks,
                locked=stack_def.get('locked', False),
                enabled=stack_def.get('enabled', True),
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
        return get_fqn(self._base_fqn, name)
