from __future__ import division
from __future__ import absolute_import
from __future__ import print_function


class Target(object):
    """A "target" is just a node in the stacker graph that does nothing, except
    specify dependencies. These can be useful as a means of logically grouping
    a set of stacks together that can be targeted with the `--targets` flag.
    """

    @classmethod
    def from_definition(cls, definition):
        return cls(name=definition.name,
                   requires=definition.requires,
                   required_by=definition.required_by,
                   logging=False)

    def __init__(self, name, requires=None, required_by=None, logging=False):
        self.name = name
        self.requires = list(requires or [])
        self.required_by = list(required_by or [])
        self.logging = logging
