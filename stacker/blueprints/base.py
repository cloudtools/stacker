import hashlib
import logging
import re
from string import Template as StringTemplate

from troposphere import Parameter, Template

from ..exceptions import (
    MissingLocalParameterException,
    OutputDoesNotExist,
    UnresolvedBlueprintParameters,
)

logger = logging.getLogger(__name__)

OUTPUT_REGEX = re.compile('([_\-a-zA-Z0-9]*::[_\-a-zA-Z0-9]*)')


class OutputTemplate(StringTemplate):
    """Template we can use to replace references to other stack's output.

    ie.

    postgres://user:password@${empire::DBCname}

    """
    idpattern = '[_a-z][_a-z0-9:\-]*'


def get_local_parameters(parameter_def, parameters):
    """Gets local parameters from parameter list.

    Given a local parameter definition, and a list of parameters, extract the
    local parameters, or use a default if provided. If the parameter isn't
    present, and there is no default, then throw an exception.

    Args:
        parameter_def (dict): A dictionary of expected/allowed parameters
            and their defaults. If a parameter is in the list, but does not
            have a default, it is considered required.
        parameters (dict): A dictionary of parameters to pull local parameters
            from.

    Returns:
        dict: A dictionary of local parameters.

    Raises:
        MissingLocalParameterException: If a parameter is defined in
            parameter_def, does not have a default, and does not exist in
            parameters.

    """
    local = {}

    for param, attrs in parameter_def.items():
        try:
            value = parameters[param]
        except KeyError:
            try:
                value = attrs["default"]
            except KeyError:
                raise MissingLocalParameterException(param)

        _type = attrs.get("type")
        if _type:
            try:
                value = _type(value)
            except ValueError:
                raise ValueError("Local parameter %s must be %s.", param,
                                 _type)
        local[param] = value

    return local

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


class Blueprint(object):
    """Base implementation for dealing with a troposphere template.

    Args:
        name (str): A name for the blueprint. If not provided, one will be
            created from the class name automatically.
        context (`stacker.context.Context`): the context the blueprint is being
            executed under.
        mappings (Optional[dict]): Cloudformation Mappings to be used in the
            template.

    """

    def __init__(self, name, context, mappings=None):
        self.name = name
        self.context = context
        self.mappings = mappings
        self.outputs = {}
        self.local_parameters = self.get_local_parameters()
        self.reset_template()
        self.resolved_parameters = None

    @property
    def parameters(self):
        return self.template.parameters

    @property
    def required_parameters(self):
        """Returns all template parameters that do not have a default value."""
        required = []
        for k, v in self.parameters.items():
            if not hasattr(v, "Default"):
                required.append((k, v))
        return required

    def get_local_parameters(self):
        local_parameters = getattr(self, "LOCAL_PARAMETERS", {})
        return get_local_parameters(local_parameters, self.context.parameters)

    def _get_parameters(self):
        """Get the parameter definitions.

        First looks at CF_PARAMETERS, then falls back to PARAMETERS for
        backwards compatibility.

        Makes this easy to override going forward for more backwards
        compatibility.

        Returns:
            dict: parameter definitions. Keys are parameter names, the values
                are dicts containing key/values for various parameter
                properties.
        """
        return getattr(self, "CF_PARAMETERS",
                       getattr(self, "PARAMETERS", {}))

    def setup_parameters(self):
        t = self.template
        parameters = self._get_parameters()

        if not parameters:
            logger.debug("No parameters defined.")
            return

        for param, attrs in parameters.items():
            p = build_parameter(param, attrs)
            t.add_parameter(p)

    def defined_parameters(self):
        """Return a dictionary of parameters defined by the blueprint.

        By default, this will just return the values from
        `BLUEPRINT_PARAMETERS`, but this makes it easy for subclasses to add
        parameters.

        Returns:
            dict: parameters defined by the blueprint

        """
        return getattr(self, "BLUEPRINT_PARAMETERS", {})

    def get_parameters(self):
        """Return a dictionary of parameters available to the template.

        These parameters will have been defined within `BLUEPRINT_PARAMETERS`
        or `self.defined_parameters`. Any parameter value that depends on stack
        output will have been resolved.

        Returns:
            dict: parameters available to the template

        """
        if self.resolved_parameters is None:
            raise UnresolvedBlueprintParameters(self)
        return self.resolved_parameters

    def resolve_parameters(self, parameter_values, provider, context):
        """Resolve the values of the blueprint parameters.

        resolve_parameters will resolve the values of the
        `BLUEPRINT_PARAMETERS` with values from the command line, the env file,
        the config, and any references to other stack output.

        Args:
            parameter_values (dict): dictionary of parameter key to parameter
                value
            provider (:class:`stacker.providers.base.BaseProvider`): provider
                to use to resolve references to output
            context (:class:`stacker.context.Context`): context to pull stack
                fqn from

        """

        def _resolve_string(value, provider, context):
            for match in OUTPUT_REGEX.finditer(value):
                # Get from the Output(s) of another stack(s) in the
                # stack_map
                stack_output = match.group()
                stack_name, output = stack_output.split("::")
                stack_fqn = context.get_fqn(stack_name)
                try:
                    output_value = provider.get_output(stack_fqn, output)
                except KeyError:
                    raise OutputDoesNotExist(stack_fqn, stack_output)
                # We do a `safe_substitute` to catch any instances of
                # `${some-stack::output}` followed by a replace for backwards
                # compatability with values like:
                # `some-stack::output,some-other-stack::output`
                value = OutputTemplate(value).safe_substitute(
                    {stack_output: output_value})
                value = value.replace(stack_output, output_value)
            return value

        def _resolve(value, provider, context):
            if isinstance(value, basestring):
                return _resolve_string(value, provider, context)
            elif isinstance(value, list):
                resolved = []
                for v in value:
                    resolved.append(_resolve(v, provider, context))
                return resolved
            elif isinstance(value, dict):
                for key, v in value.iteritems():
                    value[key] = _resolve(v, provider, context)
                return value
            return value

        self.resolved_parameters = {}
        defined_parameters = self.defined_parameters()
        for key, value in parameter_values.iteritems():
            if key not in defined_parameters:
                logger.debug("Blueprint %s does not use parameter %s.",
                             self.name, key)
                continue
            value = _resolve(value, provider, context)
            if value is None:
                logger.debug("Got None value for parameter %s, not submitting "
                             "it to cloudformation, default value should be "
                             "used.", key)
                continue
            self.resolved_parameters[key] = value

    def import_mappings(self):
        if not self.mappings:
            return

        for name, mapping in self.mappings.items():
            logger.debug("Adding mapping %s.", name)
            self.template.add_mapping(name, mapping)

    def reset_template(self):
        self.template = Template()
        self.import_mappings()
        self._rendered = None
        self._version = None

    def render_template(self):
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
