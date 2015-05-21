from .config import parse_config
from .stack import Stack


class Context(object):

    _optional_keys = ('environment', 'stack_names', 'parameters', 'mappings', 'config')

    def __init__(self, namespace, **kwargs):
        self.namespace = namespace
        for key in self._optional_keys:
            setattr(self, key, kwargs.get(key))
        self._base_fqn = namespace.replace('.', '-').lower()

    def load_config(self, conf_string):
        self.config = parse_config(conf_string, environment=self.environment)
        self.mappings = self.config['mappings']

    def _get_stack_definitions(self):
        if not self.stack_names:
            return self.config['stacks']
        return [s for s in self.config['stacks'] if s['name'] in self.stack_names]

    def get_stacks(self):
        # TODO fix docstring
        """Extract stack definitions from the config.

        If no stack_list given, return stack config as is.
        """
        if not hasattr(self, '_stacks'):
            definitions = self._get_stack_definitions()
            self._stacks = []
            for stack_def in definitions:
                stack = Stack(
                    base_fqn=self.get_fqn(),
                    definition=stack_def,
                    parameters=self.parameters,
                    mappings=self.mappings,
                )
                self._stacks.append(stack)
        return self._stacks

    def get_stacks_dict(self):
        return dict((stack.name, stack) for stack in self.get_stacks())

    def get_fqn(self, name=None):
        return '-'.join(filter(None, [self._base_fqn, name]))
