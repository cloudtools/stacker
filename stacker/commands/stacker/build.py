"""Launches or updates CloudFormation stacks based on the given config.

Stacker is smart enough to figure out if anything (the template or parameters)
have changed for a given stack. If nothing has changed, stacker will correctly
skip executing anything against the stack.

"""

from .base import BaseCommand
from ...actions import build


class Build(BaseCommand):

    name = 'build'
    description = __doc__

    def add_arguments(self, parser):
        super(Build, self).add_arguments(parser)
        parser.add_argument("-m", "--max-zones", type=int,
                            help="Gives you the ability to limit the # of "
                                 "zones that resources will be launched in. "
                                 "If not given, then resources will be "
                                 "launched in all available availability "
                                 "zones.")
        parser.add_argument("-o", "--outline", action="store_true",
                            help="Print an outline of what steps will be "
                                 "taken to build the stacks")
        parser.add_argument("--force", action="append", default=[],
                            metavar="STACKNAME", type=str,
                            help="If a stackname is provided to --force, it "
                                 "will be updated, even if it is locked in "
                                 "the config.")
        parser.add_argument("--stacks", action="append",
                            metavar="STACKNAME", type=str,
                            help="Only work on the stacks given. Can be "
                                 "specified more than once. If not specified "
                                 "then stacker will work on all stacks in the "
                                 "config file.")
        parser.add_argument('-t', '--tail', action='store_true',
                            help='Tail the CloudFormation logs while working'
                                 'with stacks')

    def run(self, options, **kwargs):
        super(Build, self).run(options, **kwargs)
        action = build.Action(options.context, provider=options.provider)
        action.execute(outline=options.outline, tail=options.tail)

    def get_context_kwargs(self, options, **kwargs):
        return {'stack_names': options.stacks, 'force_stacks': options.force}
