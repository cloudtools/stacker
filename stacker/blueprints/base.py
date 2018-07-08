from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str
from past.builtins import basestring
from builtins import object
import copy
import hashlib
import logging
import string
from stacker.util import read_value_from_path
from stacker.variables import Variable

from troposphere import (
    Output,
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
    InvalidUserdataPlaceholder
)
from .variables.types import (
    CFNType,
    TroposphereType,
)

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
            value (str, list, int or bool): the value we're going to submit as
                a CloudFormation Parameter.

        """
        acceptable_types = [basestring, bool, list, int]
        acceptable = False
        for acceptable_type in acceptable_types:
            if isinstance(value, acceptable_type):
                acceptable = True
                if acceptable_type == bool:
                    logger.debug("Converting parameter %s boolean '%s' "
                                 "to string.", name, value)
                    value = str(value).lower()
                    break

                if acceptable_type == int:
                    logger.debug("Converting parameter %s integer '%s' "
                                 "to string.", name, value)
                    value = str(value)
                    break

        if not acceptable:
            raise ValueError(
                "CFNParameter (%s) value must be one of %s got: %s" % (
                    name, "str, int, bool, or list", value))

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
        object: Returns the appropriate value object. If the original value
            was of CFNType, the returned value will be wrapped in CFNParameter.

    Raises:
        ValueError: If the `value` isn't of `var_type` and can't be cast as
            that type, this is raised.
    """

    if isinstance(var_type, CFNType):
        value = CFNParameter(name=var_name, value=value)
    elif isinstance(var_type, TroposphereType):
        try:
            value = var_type.create(value)
        except Exception as exc:
            name = "{}.create".format(var_type.resource_name)
            raise ValidatorError(var_name, name, value, exc)
    else:
        if not isinstance(value, var_type):
            raise ValueError(
                "Value for variable %s must be of type %s. Actual "
                "type: %s." % (var_name, var_type, type(value))
            )

    return value


def validate_allowed_values(allowed_values, value):
    """Support a variable defining which values it allows.

    Args:
        allowed_values (Optional[list]): A list of allowed values from the
            variable definition
        value (obj): The object representing the value provided for the
            variable

    Returns:
        bool: Boolean for whether or not the value is valid.

    """
    # ignore CFNParameter, troposphere handles these for us
    if not allowed_values or isinstance(value, CFNParameter):
        return True

    return value in allowed_values


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
    value = validate_variable_type(var_name, var_type, value)

    allowed_values = var_def.get("allowed_values")
    if not validate_allowed_values(allowed_values, value):
        message = (
            "Invalid value passed to '%s' in blueprint: %s. Got: '%s', "
            "expected one of %s"
        ) % (var_name, blueprint_name, value, allowed_values)
        raise ValueError(message)

    return value


def parse_user_data(variables, raw_user_data, blueprint_name):
    """Parse the given user data and renders it as a template

    It supports referencing template variables to create userdata
    that's supplemented with information from the stack, as commonly
    required when creating EC2 userdata files.

    For example:
        Given a raw_user_data string: 'open file ${file}'
        And a variables dictionary with: {'file': 'test.txt'}
        parse_user_data would output: open file test.txt

    Args:
        variables (dict): variables available to the template
        raw_user_data (str): the user_data to be parsed
        blueprint_name (str): the name of the blueprint

    Returns:
        str: The parsed user data, with all the variables values and
             refs replaced with their resolved values.

    Raises:
        InvalidUserdataPlaceholder: Raised when a placeholder name in
                                    raw_user_data is not valid.
                                    E.g ${100} would raise this.
        MissingVariable: Raised when a variable is in the raw_user_data that
                         is not given in the blueprint

    """
    variable_values = {}

    for key, value in variables.items():
        if type(value) is CFNParameter:
            variable_values[key] = value.to_parameter_value()
        else:
            variable_values[key] = value

    template = string.Template(raw_user_data)

    res = ""

    try:
        res = template.substitute(variable_values)
    except ValueError as exp:
        raise InvalidUserdataPlaceholder(blueprint_name, exp.args[0])
    except KeyError as key:
        raise MissingVariable(blueprint_name, key)

    return res


class Blueprint(object):

    """Base implementation for rendering a troposphere template.

    Args:
        name (str): A name for the blueprint.
        context (:class:`stacker.context.Context`): the context the blueprint
            is being executed under.
        mappings (dict, optional): Cloudformation Mappings to be used in the
            template.

    """

    def __init__(self, name, context, mappings=None, description=None):
        self.name = name
        self.context = context
        self.mappings = mappings
        self.outputs = {}
        self.reset_template()
        self.resolved_variables = None
        self.description = description

        if hasattr(self, "PARAMETERS") or hasattr(self, "LOCAL_PARAMETERS"):
            raise AttributeError("DEPRECATION WARNING: Blueprint %s uses "
                                 "deprecated PARAMETERS or "
                                 "LOCAL_PARAMETERS, rather than VARIABLES. "
                                 "Please update your blueprints. See https://"
                                 "stacker.readthedocs.io/en/latest/blueprints."
                                 "html#variables for aditional information."
                                 % name)

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
        for var_name, attrs in self.defined_variables().items():
            var_type = attrs.get("type")
            if isinstance(var_type, CFNType):
                cfn_attrs = copy.deepcopy(attrs)
                cfn_attrs["type"] = var_type.parameter_type
                output[var_name] = cfn_attrs
        return output

    def get_required_parameter_definitions(self):
        """Returns all template parameters that do not have a default value.

        Returns:
            dict: dict of required CloudFormation Parameters for the blueprint.
                Will be a dictionary of <parameter name>: <parameter
                attributes>.

        """
        required = {}
        for name, attrs in self.get_parameter_definitions().items():
            if "Default" not in attrs:
                required[name] = attrs
        return required

    def get_parameter_values(self):
        """Return a dictionary of variables with `type` :class:`CFNType`.

        Returns:
            dict: variables that need to be submitted as CloudFormation
                Parameters. Will be a dictionary of <parameter name>:
                <parameter value>.

        """
        variables = self.get_variables()
        output = {}
        for key, value in variables.items():
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
        return copy.deepcopy(getattr(self, "VARIABLES", {}))

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
        for key, value in variables.items():
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
        for var_name, var_def in defined_variables.items():
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

        for name, mapping in self.mappings.items():
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
        if self.description:
            self.set_template_description(self.description)
        self.setup_parameters()
        rendered = self.template.to_json(indent=self.context.template_indent)
        version = hashlib.md5(rendered.encode()).hexdigest()[:8]
        return (version, rendered)

    def to_json(self, variables=None):
        """Render the blueprint and return the template in json form.

        Args:
            variables (dict):
                Optional dictionary providing/overriding variable values.

        Returns:
            str: the rendered CFN JSON template
        """

        variables_to_resolve = []
        if variables:
            for key, value in variables.items():
                variables_to_resolve.append(Variable(key, value))
        for k in self.get_parameter_definitions():
            if not variables or k not in variables:
                # The provided value for a CFN parameter has no effect in this
                # context (generating the CFN template), so any string can be
                # provided for its value - just needs to be something
                variables_to_resolve.append(Variable(k, 'unused_value'))
        self.resolve_variables(variables_to_resolve)

        return self.render_template()[1]

    def read_user_data(self, user_data_path):
        """Reads and parses a user_data file.

        Args:
            user_data_path (str):
                path to the userdata file

        Returns:
            str: the parsed user data file

        """
        raw_user_data = read_value_from_path(user_data_path)

        variables = self.get_variables()

        return parse_user_data(variables, raw_user_data, self.name)

    def set_template_description(self, description):
        """Adds a description to the Template

        Args:
            description (str): A description to be added to the resulting
                template.

        """
        self.template.add_description(description)

    def add_output(self, name, value):
        """Simple helper for adding outputs.

        Args:
            name (str): The name of the output to create.
            value (str): The value to put in the output.
        """
        self.template.add_output(Output(name, Value=value))

    @property
    def requires_change_set(self):
        """Returns true if the underlying template has transforms."""
        return self.template.transform is not None

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
