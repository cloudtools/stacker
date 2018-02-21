"""Blueprint representing raw template module."""

import hashlib
import json

from ..util import parse_cloudformation_template
from ..exceptions import MissingVariable, UnresolvedVariable


def get_template_params(template):
    """Parse a CFN template for defined parameters.

    Args:
        template (dict): Parsed CFN template.

    Returns:
        dict: Template parameters.

    """
    params = {}

    if 'Parameters' in template:
        params = template['Parameters']
    return params


def resolve_variable(var_name, var_def, provided_variable, blueprint_name):
    """Resolve a provided variable value against the variable definition.

    This acts as a subset of resolve_variable logic in the base module, leaving
    out everything that doesn't apply to CFN parameters.

    Args:
        var_name (str): The name of the defined variable on a blueprint.
        var_def (dict): A dictionary representing the defined variables
            attributes.
        provided_variable (:class:`stacker.variables.Variable`): The variable
            value provided to the blueprint.
        blueprint_name (str): The name of the blueprint that the variable is
            being applied to.

    Returns:
        object: The resolved variable string value.

    Raises:
        MissingVariable: Raised when a variable with no default is not
            provided a value.
        UnresolvedVariable: Raised when the provided variable is not already
            resolved.

    """
    if provided_variable:
        if not provided_variable.resolved:
            raise UnresolvedVariable(blueprint_name, provided_variable)

        value = provided_variable.value
    else:
        # Variable value not provided, try using the default, if it exists
        # in the definition
        try:
            value = var_def["Default"]
        except KeyError:
            raise MissingVariable(blueprint_name, var_name)

    return value


class RawTemplateBlueprint(object):
    """Blueprint class for blueprints auto-generated from raw templates."""

    def __init__(self, name, context, raw_template_path, mappings=None, # noqa pylint: disable=too-many-arguments
                 description=None):  # pylint: disable=unused-argument
        """Initialize RawTemplateBlueprint object."""
        self.name = name
        self.context = context
        self.mappings = mappings
        self.resolved_variables = None
        self.raw_template_path = raw_template_path
        self._rendered = None
        self._version = None

    def to_json(self, variables=None):  # pylint: disable=unused-argument
        """Return the template in JSON.

        Args:
            variables (dict):
                Unused in this subclass (variables won't affect the template).

        Returns:
            str: the rendered CFN JSON template

        """
        # load -> dumps will produce json from json or yaml templates
        return json.dumps(self.to_dict(), sort_keys=True, indent=4)

    def to_dict(self):
        """Return the template as a python dictionary.

        Returns:
            dict: the loaded template as a python dictionary

        """
        return parse_cloudformation_template(self.rendered)

    def render_template(self):
        """Load template and generate its md5 hash."""
        return (self.version, self.rendered)

    def get_parameter_definitions(self):
        """Get the parameter definitions to submit to CloudFormation.

        Returns:
            dict: parameter definitions. Keys are parameter names, the values
                are dicts containing key/values for various parameter
                properties.

        """
        return get_template_params(self.to_dict())

    def resolve_variables(self, provided_variables):
        """Resolve the values of the blueprint variables.

        This will resolve the values of the template parameters with values
        from the env file, the config, and any lookups resolved.

        Args:
            provided_variables (list of :class:`stacker.variables.Variable`):
                list of provided variables

        """
        self.resolved_variables = {}
        defined_variables = self.get_parameter_definitions()
        variable_dict = dict((var.name, var) for var in provided_variables)
        for var_name, var_def in defined_variables.iteritems():
            value = resolve_variable(
                var_name,
                var_def,
                variable_dict.get(var_name),
                self.name
            )
            self.resolved_variables[var_name] = value

    def get_parameter_values(self):
        """Return a dictionary of variables with `type` :class:`CFNType`.

        Returns:
            dict: variables that need to be submitted as CloudFormation
                Parameters. Will be a dictionary of <parameter name>:
                <parameter value>.

        """
        return self.resolved_variables

    def get_required_parameter_definitions(self):  # noqa pylint: disable=invalid-name
        """Return all template parameters that do not have a default value.

        Returns:
            dict: dict of required CloudFormation Parameters for the blueprint.
                Will be a dictionary of <parameter name>: <parameter
                attributes>.

        """
        required = {}
        for i in list(self.get_parameter_definitions().items()):
            if i[1].get('Default', None) is None:
                required[i[0]] = i[1]
        return required

    @property
    def requires_change_set(self):
        """Return True if the underlying template has transforms."""
        return bool("Transform" in self.to_dict())

    @property
    def rendered(self):
        """Return (generating first if needed) rendered template."""
        if not self._rendered:
            with open(self.raw_template_path, 'r') as template:
                self._rendered = template.read()
        return self._rendered

    @property
    def version(self):
        """Return (generating first if needed) version hash."""
        if not self._version:
            self._version = hashlib.md5(self.rendered).hexdigest()[:8]
        return self._version
