import logging
import hashlib

logger = logging.getLogger(__name__)

from troposphere import Template


class StackTemplateBase(object):
    """Base implementation for dealing with a troposphere template.

    :type region: string, AWS region
    :param region: The AWS region where this stack will be deployed.

    :type name: string
    :param name: A name for the stack template. If not provided, one
        will be created from the class name automatically.

    :type mappings: dict
    :param mappings: Cloudformation Mappings to be used in the template.

    :type config: dict
    :param config: A dictionary which is used to pass in configuration info
        to the stack.
    """
    def __init__(self, region, name=None, mappings=None, config=None):
        self.region = region
        if not name:
            name = self.__class__.__name__.lower()
        self.name = name
        self.mappings = mappings
        self.config = config or {}
        self.outputs = {}
        self.reset_template()

    @property
    def parameters(self):
        params = []
        for param in self.template.parameters:
            try:
                params.append((param, self.config[param]))
            except KeyError:
                logger.debug("Parameter '%s' not found in config, skipping.",
                             param)
                continue
        return params

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
        self.reset_template()
        self.create_template()
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
