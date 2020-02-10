from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import copy
import logging

from . import util
from .variables import (
    Variable,
    resolve_variables,
)

from .blueprints.raw import RawTemplateBlueprint

logger = logging.getLogger(__name__)


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
        stack_def (:class:`stacker.config.Stack`): The stack definition being
            worked on.

    Returns:
        :obj:`list` of :class:`stacker.variables.Variable`: Contains key/value
            pairs of the collected  variables.

    Raises:
        AttributeError: Raised when the stack definition contains an invalid
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
        mappings (dict, optional): CloudFormation mappings passed to the
            blueprint.
        force (bool, optional): Whether to force updates on this stack.

    """

    def __init__(self, definition, context, mappings=None, force=False):
        self.logging = True
        self.name = definition.name
        self.fqn = context.get_fqn(definition.stack_name or self.name)
        self.region = definition.region
        self.profile = definition.profile
        self.locked = definition.locked
        self.enabled = definition.enabled
        self.protected = definition.protected
        self.definition = definition
        self.variables = _gather_variables(definition)
        self.mappings = mappings
        self.force = force
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

    def should_submit(self):
        """Tests whether this stack should be submitted to CF

        Returns:
            bool: If the stack should be submitted, return True.

        """

        if self.enabled:
            return True

        logger.debug("Stack %s is not enabled.  Skipping.", self.name)
        return False

    def should_update(self):
        """Tests whether this stack should be submitted for updates to CF.

        Returns:
            bool: If the stack should be updated, return True.

        """

        if self.locked:
            if not self.force:
                logger.debug("Stack %s locked and not in --force list. "
                             "Refusing to update.", self.name)
                return False
            else:
                logger.debug("Stack %s locked, but is in --force "
                             "list.", self.name)
        return True


class ExternalStack(Stack):
    """Represents gathered information about an existing external stack

    Args:
        definition (:class:`stacker.config.ExternalStack`): A stack definition.
        context (:class:`stacker.context.Context`): Current context for
            building the stack.

    """

    def __init__(self, definition, context):
        self.name = definition.name
        stack_name = definition.stack_name or self.name
        self.fqn = definition.fqn or context.get_fqn(stack_name)
        self.region = definition.region
        self.profile = definition.profile
        self.definition = definition
        self.context = context
        self.outputs = None

    @property
    def requires(self):
        return set()

    @property
    def stack_policy(self):
        return None

    @property
    def blueprint(self):
        return None

    @property
    def tags(self):
        return dict()

    @property
    def parameter_values(self):
        return dict()

    @property
    def required_parameter_definitions(self):
        return dict()

    def resolve(self, context, provider):
        pass

    def set_outputs(self, outputs):
        self.outputs = outputs

    def should_submit(self):
        # Always submit this stack to load outputs
        return True

    def should_update(self):
        # Never update an external stack
        return False
