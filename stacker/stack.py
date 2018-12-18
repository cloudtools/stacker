from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import copy

from . import util
from .variables import (
    Variable,
    resolve_variables,
)

from .blueprints.raw import RawTemplateBlueprint


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
    return [Variable(k, v) for k, v in variable_values.items()]


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
        self.logging = True
        self.name = definition.name
        self.fqn = context.get_fqn(definition.stack_name or self.name)
        self.region = definition.region
        self.profile = definition.profile
        self.definition = definition
        self.variables = _gather_variables(definition)
        self.mappings = mappings
        self.locked = locked
        self.force = force
        self.enabled = enabled
        self.protected = protected
        self.context = context
        self.outputs = None
        self.in_progress_behavior = definition.in_progress_behavior

    def __repr__(self):
        return self.fqn

    @property
    def required_by(self):
        return self.definition.required_by or []

    @property
    def requires(self):
        # By definition, a locked stack has no dependencies, because we won't
        # be performing an update operation on the stack. This means, resolving
        # outputs from dependencies is unnecessary.
        if self.locked and not self.force:
            return []

        requires = set(self.definition.requires or [])

        # Add any dependencies based on output lookups
        for variable in self.variables:
            deps = variable.dependencies()
            if self.name in deps:
                message = (
                    "Variable %s in stack %s has a circular reference"
                ) % (variable.name, self.name)
                raise ValueError(message)
            requires.update(deps)
        return requires

    @property
    def stack_policy(self):
        if not hasattr(self, "_stack_policy"):
            self._stack_policy = None
            if self.definition.stack_policy_path:
                with open(self.definition.stack_policy_path) as f:
                    self._stack_policy = f.read()

        return self._stack_policy

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
    def all_parameter_definitions(self):
        """Return a list of all parameters in the blueprint/template."""
        return self.blueprint.get_parameter_definitions()

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

    def set_outputs(self, outputs):
        self.outputs = outputs
