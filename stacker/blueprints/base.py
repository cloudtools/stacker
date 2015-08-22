import hashlib
import logging

from troposphere import Parameter, Template

from ..exceptions import MissingLocalParameterException

logger = logging.getLogger(__name__)


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
                value = attrs['default']
            except KeyError:
                raise MissingLocalParameterException(param)
        local[param] = value

    return local


def build_parameter(name, attrs):
    """Builds a troposphere Parameter with the given attributes.

    Args:
        name (string): The name of the parameter.
        attrs (dict): Contains the attributes that will be applied to the
            parameter. See:
            http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html

    Returns:
        :class:`troposphere.Parameter`: The created parameter object.
    """
    p = Parameter(name,
                  Type=attrs.get('type'),
                  Description=attrs.get('description', ''))
    if 'default' in attrs:
        p.Default = attrs['default']
    if 'no_echo' in attrs:
        p.NoEcho = attrs['no_echo']
    if 'allowed_values' in attrs:
        p.AllowedValues = attrs['allowed_values']
    if 'allowed_pattern' in attrs:
        p.AllowedPattern = attrs['allowed_pattern']
    if 'max_length' in attrs:
        p.MaxLength = attrs['max_length']
    if 'min_length' in attrs:
        p.MinLength = attrs['min_length']
    if 'max_value' in attrs:
        p.MaxValue = attrs['max_value']
    if 'min_value' in attrs:
        p.MinValue = attrs['min_value']
    if 'constraint_description' in attrs:
        p.ConstraintDescription = attrs['constraint_description']
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

    @property
    def parameters(self):
        return self.template.parameters

    @property
    def required_parameters(self):
        """Returns all template parameters that do not have a default value."""
        required = []
        for k, v in self.parameters.items():
            if not hasattr(v, 'Default'):
                required.append((k, v))
        return required

    def get_local_parameters(self):
        local_parameters = getattr(self, 'LOCAL_PARAMETERS', {})
        return get_local_parameters(local_parameters, self.context.parameters)

    def setup_parameters(self):
        t = self.template
        # First look for CF_PARAMETERS, then fall back to regular PARAMETERS
        # for backwards compatibility.
        parameters = getattr(self, 'CF_PARAMETERS',
                             getattr(self, 'PARAMETERS', {}))

        if not parameters:
            logger.debug("No parameters defined.")
            return

        for param, attrs in parameters.items():
            p = build_parameter(param, attrs)
            t.add_parameter(p)

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
