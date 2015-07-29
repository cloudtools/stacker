from .exceptions import MissingEnvironment
from .config import parse_config
from .stack import Stack


class Context(object):
    """The context under which the current stacks are being executed.

    The stacker Context is responsible for translating the values passed in via
    the command line and specified in the config to `Stack` objects.

    """

    _optional_keys = ('stack_names', 'parameters', 'mappings', 'config')

    def __init__(self, environment, **kwargs):
        try:
            self.namespace = environment['namespace']
        except KeyError:
            raise MissingEnvironment(['namespace'])

        self.environment = environment
        for key in self._optional_keys:
            setattr(self, key, kwargs.get(key))

        self._base_fqn = self.namespace.replace('.', '-').lower()

    def load_config(self, conf_string):
        self.config = parse_config(conf_string, environment=self.environment)
        self.mappings = self.config['mappings']

    def _get_stack_definitions(self):
        if not self.stack_names:
            return self.config['stacks']
        return [s for s in self.config['stacks'] if s['name'] in self.stack_names]

    def get_stacks(self):
        """Get the stacks for the current action.

        Handles configuring the `stacker.stack.Stack` objects that will be used
        in the current action. Responsible for merging the stack definition in
        the config, the parameters specified on the command line, and any
        mappings specified in the config.

        Returns:
            list: a list of `stacker.stack.Stack` objects

        """
        if not hasattr(self, '_stacks'):
            definitions = self._get_stack_definitions()
            self._stacks = []
            for stack_def in definitions:
                stack = Stack(
                    definition=stack_def,
                    context=self,
                    parameters=self.parameters,
                    mappings=self.mappings,
                )
                self._stacks.append(stack)
        return self._stacks

    def get_stacks_dict(self):
        return dict((stack.fqn, stack) for stack in self.get_stacks())

    def get_fqn(self, name=None):
        """Return the fully qualified name of an object within this context.

        If the name passed already appears to be a fully qualified name, it
        will be returned with no further processing.

        """
        if name and name.startswith(self._base_fqn + '-'):
            return name

        return '-'.join(filter(None, [self._base_fqn, name]))
