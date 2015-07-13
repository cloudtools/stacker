# TODO make sure this is still relevant
"""Launches or updates cloudformation stacks based on the given config.

The script is smart enough to figure out if anything (the template, or
parameters) has changed for a given stack. If not, it will skip that stack.

Can also pull parameters from other stack's outputs.
"""

from .base import StackerCommand
from ...actions import build


class Build(StackerCommand):

    name = 'build'
    description = __doc__

    def add_arguments(self, parser):
        super(Build, self).add_arguments(parser)
        parser.add_argument('-m', '--max-zones', type=int,
                            help="Gives you the ability to limit the # of zones "
                                 "that resources will be launched in. If not "
                                 "given, then resources will be launched in all "
                                 "available availability zones.")
        parser.add_argument('-o', '--outline', action='store_true',
                            help='Print an outline of what steps will be taken '
                            'to build the stacks')

    def run(self, options, **kwargs):
        super(Build, self).run(options, **kwargs)
        action = build.Action(options.context, provider=options.provider)
        action.execute(outline=options.outline)
