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

from .blueprints.raw import RawTemplateBlueprint
from .exceptions import FailedVariableLookup


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
    variable_values = copy.deepcopy(stack_def.variables or {})
    return [Variable(k, v) for k, v in variable_values.iteritems()]


class Stack(object):

    """Represents gathered information about a stack to be built/updated.

    Args:
        definition (:class:`stacker.config.Stack`): A stack definition.
        context (:class:`stacker.context.Context`): Current context for
            building the stack.
        mappings (dict, optional): Cloudformation mappings passed to the
            blueprint.
        locked (bool, optional): Whether or not the stack is locked.
        force (bool, optional): Whether to force updates on this stack.
        enabled (bool, optional): Whether this stack is enabled

    """

    def __init__(self, definition, context, variables=None, mappings=None,
                 locked=False, force=False, enabled=True, protected=False):
        self.name = definition.name
        self.fqn = context.get_fqn(self.name)
        self.definition = definition
        self.variables = _gather_variables(definition)
        self.mappings = mappings
        self.locked = locked
        self.force = force
        self.enabled = enabled
        self.protected = protected
        self.context = copy.deepcopy(context)

    def __repr__(self):
        return self.fqn

    @property
    def requires(self):
        requires = set([self.context.get_fqn(r) for r in
                        self.definition.requires or []])

        # Add any dependencies based on output lookups
        for variable in self.variables:
            for lookup in variable.lookups:
                if lookup.type == OUTPUT_LOOKUP_TYPE_NAME:

                    try:
                        d = deconstruct(lookup.input)
                    except ValueError as e:
                        raise FailedVariableLookup(self.name, e)

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
            kwargs = {}
            blueprint_class = None
            if self.definition.class_path:
                class_path = self.definition.class_path
                blueprint_class = util.load_object_from_string(class_path)
                if not hasattr(blueprint_class, "rendered"):
                    raise AttributeError("Stack class %s does not have a "
                                         "\"rendered\" "
                                         "attribute." % (class_path,))
            elif self.definition.template_path:
                blueprint_class = RawTemplateBlueprint
                kwargs["raw_template_path"] = self.definition.template_path
            else:
                raise AttributeError("Stack does not have a defined class or "
                                     "template path.")

            self._blueprint = blueprint_class(
                name=self.name,
                context=self.context,
                mappings=self.mappings,
                description=self.definition.description,
                **kwargs
            )
        return self._blueprint

    @property
    def tags(self):
        """Returns the tags that should be set on this stack. Includes both the
        global tags, as well as any stack specific tags or overrides.

        Returns:

            dict: dictionary of tags

        """
        tags = self.definition.tags or {}
        return dict(self.context.tags, **tags)

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
