"""Blueprint representing raw template module."""

import hashlib

from .base import Blueprint


class RawTemplateBlueprint(Blueprint):
    """Blueprint class for blueprints auto-generated from raw templates."""

    def __init__(self, name, context,  # pylint: disable=too-many-arguments
                 raw_template_path, mappings=None, description=None):
        """Add raw_template_path to base blueprint class."""
        super(RawTemplateBlueprint, self).__init__(name,
                                                   context,
                                                   mappings,
                                                   description)
        self._raw_template_path = raw_template_path

    def create_template(self):
        """Override base blueprint create_template with a noop."""
        # Don't actually need to do anything here since it won't be called from
        # render_template
        pass

    def render_template(self):
        """Load template and generate its md5 hash."""
        if self.description:
            self.set_template_description(self.description)
        with open(self.raw_template_path, 'r') as myfile:
            rendered = myfile.read()
        version = hashlib.md5(rendered).hexdigest()[:8]
        return (version, rendered)

    @property
    def raw_template_path(self):
        """Return raw_template_path."""
        return self._raw_template_path
