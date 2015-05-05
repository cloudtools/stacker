import logging
import hashlib

logger = logging.getLogger(__name__)

from troposphere import Template, Parameter


class Blueprint(object):
    """Base implementation for dealing with a troposphere template.

    :type name: string
    :param name: A name for the blueprint. If not provided, one
        will be created from the class name automatically.

    :type context: BlueprintContext object
    :param context: Used for configuring the Blueprint.

    :type mappings: dict
    :param mappings: Cloudformation Mappings to be used in the template.

    """
    def __init__(self, name, context, mappings=None):
        self.name = name
        self.mappings = mappings
        # TODO: This is only, currently, used for parameters. should probably
        #       just pass parameters alone.
        self.context = context
        self.outputs = {}
        self.reset_template()

    @property
    def parameters(self):
        return self.template.parameters

    @property
    def required_parameters(self):
        """ Returns all parameters that do not have a default value. """
        required = []
        for k, v in self.parameters.items():
            if not hasattr(v, 'Default'):
                required.append((k, v))
        return required

    def setup_parameters(self):
        t = self.template
        parameters = getattr(self, 'PARAMETERS')
        if not parameters:
            logger.debug("No parameters defined.")
            return
        for param, attrs in parameters.items():
            p = Parameter(param,
                          Type=attrs.get('type'),
                          Description=attrs.get('description', ''))
            if 'default' in attrs:
                p.Default = attrs['default']
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
