import copy
import hashlib
import logging

from troposphere import (
    Parameter,
    Ref,
    Template,
)

from ..exceptions import (
    MissingVariable,
    UnresolvedVariable,
    UnresolvedVariables,
    ValidatorError,
    VariableTypeRequired,
)
from .variables.types import CFNType

logger = logging.getLogger(__name__)

PARAMETER_PROPERTIES = {
    "default": "Default",
    "description": "Description",
    "no_echo": "NoEcho",
    "allowed_values": "AllowedValues",
    "allowed_pattern": "AllowedPattern",
    "max_length": "MaxLength",
    "min_length": "MinLength",
    "max_value": "MaxValue",
    "min_value": "MinValue",
    "constraint_description": "ConstraintDescription"
}


class CFNParameter(object):

    def __init__(self, name, value):
        """Wrapper around a value to indicate a CloudFormation Parameter.

        Args:
            name (str): the name of the CloudFormation Parameter
            value (str or list): the value we're going to submit as a
                CloudFormation Parameter.

        """
        acceptable_types = [basestring, list, int]
        acceptable = False
        for acceptable_type in acceptable_types:
            if isinstance(value, acceptable_type):
                # Convert integers to strings
                if acceptable_type == int:
                    value = str(value)

                acceptable = True

        if not acceptable:
            raise ValueError(
                "CFNParameter (%s) value must be one of %s got: %s" % (
                    name, "str, int, or list", value))

        self.name = name
        self.value = value

    def __repr__(self):
        return "CFNParameter({}: {})".format(self.name, self.value)

    def to_parameter_value(self):
        """Return the value to be submitted to CloudFormation"""
        return self.value

    @property
    def ref(self):
        return Ref(self.name)


def build_parameter(name, properties):
    """Builds a troposphere Parameter with the given properties.

    Args:
        name (string): The name of the parameter.
        properties (dict): Contains the properties that will be applied to the
            parameter. See:
            http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html

    Returns:
        :class:`troposphere.Parameter`: The created parameter object.
    """
    p = Parameter(name, Type=properties.get("type"))
    for name, attr in PARAMETER_PROPERTIES.items():
        if name in properties:
            setattr(p, attr, properties[name])
    return p


def validate_variable_type(var_name, var_type, value):
    """Ensures the value is the correct variable type.

    Args:
        var_name (str): The name of the defined variable on a blueprint.
        var_type (type): The type that the value should be.
        value (obj): The object representing the value provided for the
            variable

    Returns:
        object: A python object of type `var_type` based on the provided
            `value`.

    Raises:
        ValueError: If the `value` isn't of `var_type` and can't be cast as
            that type, this is raised.
    """

    if isinstance(var_type, CFNType):
        value = CFNParameter(name=var_name, value=value)
    else:
        if not isinstance(value, var_type):
            try:
                value = var_type(value)
            except ValueError:
                raise ValueError("Variable %s must be %s.",
                                 var_name, var_type)
    return value


def resolve_variable(var_name, var_def, provided_variable, blueprint_name):
    """Resolve a provided variable value against the variable definition.

    Args:
        var_name (str): The name of the defined variable on a blueprint.
        var_def (dict): A dictionary representing the defined variables
            attributes.
        provided_variable (:class:`stacker.variables.Variable`): The variable
            value provided to the blueprint.
        blueprint_name (str): The name of the blueprint that the variable is
            being applied to.

    Returns:
        object: The resolved variable value, could be any python object.

    Raises:
        MissingVariable: Raised when a variable with no default is not
            provided a value.
        UnresolvedVariable: Raised when the provided variable is not already
            resolved.
        ValueError: Raised when the value is not the right type and cannot be
            cast as the correct type. Raised by
            :func:`stacker.blueprints.base.validate_variable_type`
        ValidatorError: Raised when a validator raises an exception. Wraps the
            original exception.
    """

    try:
        var_type = var_def["type"]
    except KeyError:
        raise VariableTypeRequired(blueprint_name, var_name)

    if provided_variable:
        if not provided_variable.resolved:
            raise UnresolvedVariable(blueprint_name, provided_variable)
        if provided_variable.value is not None:
            value = provided_variable.value
    else:
        # Variable value not provided, try using the default, if it exists
        # in the definition
        try:
            value = var_def["default"]
        except KeyError:
            raise MissingVariable(blueprint_name, var_name)

    # If no validator, return the value as is, otherwise apply validator
    validator = var_def.get("validator", lambda v: v)
    try:
        value = validator(value)
    except Exception as exc:
        raise ValidatorError(var_name, validator.__name__, value, exc)

    # Ensure that the resulting value is the correct type
    var_type = var_def.get("type")
    value = validate_variable_type(var_name, var_type, value)

    return value


class Blueprint(object):
    """Base implementation for rendering a troposphere template.

    Args:
        name (str): A name for the blueprint.
        context (:class:`stacker.context.Context`): the context the blueprint
            is being executed under.
        mappings (dict, optional): Cloudformation Mappings to be used in the
            template.

    """

    def __init__(self, name, context, mappings=None):
        self.name = name
        self.context = context
        self.mappings = mappings
        self.outputs = {}
        self.reset_template()
        self.resolved_variables = None

    def get_required_parameter_definitions(self):
        """Returns all template parameters that do not have a default value.

        Returns:
            dict: dict of required CloudFormation Parameters for the blueprint.
                Will be a dictionary of <parameter name>: <parameter
                attributes>.

        """
        required = {}
        for name, attrs in self.template.parameters.iteritems():
            if not hasattr(attrs, "Default"):
                required[name] = attrs
        return required

    def get_parameter_definitions(self):
        """Get the parameter definitions to submit to CloudFormation.

        Any variable definition whose `type` is an instance of `CFNType` will
        be returned as a CloudFormation Parameter.

        Returns:
            dict: parameter definitions. Keys are parameter names, the values
                are dicts containing key/values for various parameter
                properties.

        """
        output = {}
        for var_name, attrs in self.defined_variables().iteritems():
            var_type = attrs.get("type")
            if isinstance(var_type, CFNType):
                cfn_attrs = copy.deepcopy(attrs)
                cfn_attrs["type"] = var_type.parameter_type
                output[var_name] = cfn_attrs
        return output

    def get_parameter_values(self):
        """Return a dictionary of variables with `type` :class:`CFNType`.

        Returns:
            dict: variables that need to be submitted as CloudFormation
                Parameters. Will be a dictionary of <parameter name>:
                <parameter value>.

        """
        variables = self.get_variables()
        output = {}
        for key, value in variables.iteritems():
            try:
                output[key] = value.to_parameter_value()
            except AttributeError:
                continue

        return output

    def setup_parameters(self):
        """Add any CloudFormation parameters to the template"""
        t = self.template
        parameters = self.get_parameter_definitions()

        if not parameters:
            logger.debug("No parameters defined.")
            return

        for name, attrs in parameters.items():
            p = build_parameter(name, attrs)
            t.add_parameter(p)

    def defined_variables(self):
        """Return a dictionary of variables defined by the blueprint.

        By default, this will just return the values from `VARIABLES`, but this
        makes it easy for subclasses to add variables.

        Returns:
            dict: variables defined by the blueprint

        """
        return getattr(self, "VARIABLES", {})

    def get_variables(self):
        """Return a dictionary of variables available to the template.

        These variables will have been defined within `VARIABLES` or
        `self.defined_variables`. Any variable value that contains a lookup
        will have been resolved.

        Returns:
            dict: variables available to the template

        Raises:

        """
        if self.resolved_variables is None:
            raise UnresolvedVariables(self.name)
        return self.resolved_variables

    def get_cfn_parameters(self):
        """Return a dictionary of variables with `type` :class:`CFNType`.

        Returns:
            dict: variables that need to be submitted as CloudFormation
                Parameters.

        """
        variables = self.get_variables()
        output = {}
        for key, value in variables.iteritems():
            if hasattr(value, "to_parameter_value"):
                output[key] = value.to_parameter_value()
        return output

    def resolve_variables(self, provided_variables):
        """Resolve the values of the blueprint variables.

        This will resolve the values of the `VARIABLES` with values from the
        env file, the config, and any lookups resolved.

        Args:
            provided_variables (list of :class:`stacker.variables.Variable`):
                list of provided variables

        """
        self.resolved_variables = {}
        defined_variables = self.defined_variables()
        variable_dict = dict((var.name, var) for var in provided_variables)
        for var_name, var_def in defined_variables.iteritems():
            value = resolve_variable(
                var_name,
                var_def,
                variable_dict.get(var_name),
                self.name
            )
            self.resolved_variables[var_name] = value

    def import_mappings(self):
        if not self.mappings:
            return

        for name, mapping in self.mappings.iteritems():
            logger.debug("Adding mapping %s.", name)
            self.template.add_mapping(name, mapping)

    def reset_template(self):
        self.template = Template()
        self._rendered = None
        self._version = None

    def render_template(self):
        """Render the Blueprint to a CloudFormation template"""
        self.import_mappings()
        self.create_template()
        self.setup_parameters()
        rendered = self.template.to_json()
        version = hashlib.md5(rendered).hexdigest()[:8]
        return (version, rendered)

    @property
    def rendered(self):
        if not self._rendered:
            self._version, self._rendered = self.render_template()
        return self._rendered

    @property
    def version(self):
        if not self._version:
            self._version, self._rendered = self.render_template()
        return self._version

    def create_template(self):
        raise NotImplementedError
