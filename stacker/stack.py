import copy

from . import util
from .variables import (
    Variable,
    resolve_variables,
)
from .lookups.handlers.output import (
    TYPE_NAME as OUTPUT_LOOKUP_TYPE_NAME,
    deconstruct,
)


def _gather_variables(stack_def):
    """Merges context provided & stack defined variables.

    If multiple stacks have a variable with the same name, we can specify the
    value for a specific stack by passing in the variable name as: `<stack
    name>::<variable name>`. This variable value will only be used for that
    specific stack.

    Order of precedence:
        - context defined stack specific variables (ie.
            SomeStack::SomeVariable)
        - context defined non-specific variables
        - variable defined within the stack definition

    Args:
        stack_def (dict): The stack definition being worked on.

    Returns:
        dict: Contains key/value pairs of the collected variables.

    Raises:
        AttributeError: Raised when the stack definitition contains an invalid
            attribute. Currently only when using old parameters, rather than
            variables.
    """
    stack_name = stack_def["name"]
    if "parameters" in stack_def:
        raise AttributeError("Stack definition %s contains deprecated "
                             "'parameters', rather than 'variables'. Please "
                             "update your config." % stack_name)
    variable_values = copy.deepcopy(stack_def.get('variables', {}))
    return [Variable(k, v) for k, v in variable_values.iteritems()]


class Stack(object):
    """Represents gathered information about a stack to be built/updated.

    Args:
        definition (dict): A stack definition.
        context (:class:`stacker.context.Context`): Current context for
            building the stack.
        mappings (dict, optional): Cloudformation mappings passed to the
            blueprint.
        locked (bool, optional): Whether or not the stack is locked.
        force (bool, optional): Whether to force updates on this stack.
        enabled (bool, optional): Whether this stack is enabled

    """

    def __init__(self, definition, context, variables=None, mappings=None,
                 locked=False, force=False, enabled=True):
        self.name = definition["name"]
        self.fqn = context.get_fqn(self.name)
        self.definition = definition
        self.variables = _gather_variables(definition)
        self.mappings = mappings
        self.locked = locked
        self.force = force
        self.enabled = enabled
        self.context = copy.deepcopy(context)

    def __repr__(self):
        return self.fqn

    @property
    def requires(self):
        requires = set([self.context.get_fqn(r) for r in
                        self.definition.get("requires", [])])

        # Add any dependencies based on output lookups
        for variable in self.variables:
            for lookup in variable.lookups:
                if lookup.type == OUTPUT_LOOKUP_TYPE_NAME:
                    d = deconstruct(lookup.input)
                    if d.stack_name == self.name:
                        message = (
                            "Variable %s in stack %s has a ciruclar reference "
                            "within lookup: %s"
                        ) % (variable.name, self.name, lookup.raw)
                        raise ValueError(message)
                    stack_fqn = self.context.get_fqn(d.stack_name)
                    requires.add(stack_fqn)

        return requires

    @property
    def blueprint(self):
        if not hasattr(self, "_blueprint"):
            class_path = self.definition["class_path"]
            blueprint_class = util.load_object_from_string(class_path)
            if not hasattr(blueprint_class, "rendered"):
                raise AttributeError("Stack class %s does not have a "
                                     "\"rendered\" "
                                     "attribute." % (class_path,))
            self._blueprint = blueprint_class(
                name=self.name,
                context=self.context,
                mappings=self.mappings,
            )
        return self._blueprint

    @property
    def parameter_values(self):
        """Return all CloudFormation Parameters for the stack.

        CloudFormation Parameters can be specified via Blueprint Variables with
        a :class:`stacker.blueprints.variables.types.CFNType` `type`.

        Returns:
            dict: dictionary of <parameter name>: <parameter value>.

        """
        return self.blueprint.get_parameter_values()

    @property
    def required_parameter_definitions(self):
        """Return all the required CloudFormation Parameters for the stack."""
        return self.blueprint.get_required_parameter_definitions()

    def resolve(self, context, provider):
        """Resolve the Stack variables.

        This resolves the Stack variables and then prepares the Blueprint for
        rendering by passing the resolved variables to the Blueprint.

        Args:
            context (:class:`stacker.context.Context`): stacker context
            provider (:class:`stacker.provider.base.BaseProvider`): subclass of
                the base provider

        """
        resolve_variables(self.variables, context, provider)
        self.blueprint.resolve_variables(self.variables)
