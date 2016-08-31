==========
Blueprints
==========

Blueprints are python classes that build CloudFormation templates.
Traditionally these are built using troposphere_, but that is not absolutely
necessary. You are encouraged to check out the library of publicly shared
Blueprints in the stacker_blueprints_ package.

Making your own should be easy, and you can take a lot of examples from
stacker_blueprints_. In the end, all that is required is that the Blueprint
is a subclass of *stacker.blueprints.base* and it have the following methods::

    # Initializes the blueprint
    def __init__(self, name, context, mappings=None):

    # Updates self.template to create the actual template
    def create_template(self):

    # Returns a tuple: (version, rendered_template)
    def render_template(self):


.. _troposphere: https://github.com/cloudtools/troposphere
.. _stacker_blueprints: https://github.com/remind101/stacker_blueprints
