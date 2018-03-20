from __future__ import division
from __future__ import absolute_import
from __future__ import print_function


class Target(object):
    """A "target" is just a node in the stacker graph that does nothing, except
    specify dependencies. These can be useful as a means of logically grouping
    a set of stacks together that can be targeted with the `--targets` flag.
    """

    def __init__(self, definition):
        self.name = definition.name
        self.requires = definition.requires or []
        self.required_by = definition.required_by or []
        self.logging = False
