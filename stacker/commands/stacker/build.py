"""Launches or updates CloudFormation stacks based on the given config.

Stacker is smart enough to figure out if anything (the template or parameters)
have changed for a given stack. If nothing has changed, stacker will correctly
skip executing anything against the stack.

"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from .base import BaseCommand, cancel
from ...actions import build


class Build(BaseCommand):

    name = "build"
    description = __doc__

    def add_arguments(self, parser):
        super(Build, self).add_arguments(parser)
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
                            help="Only work on the stacks given, and their "
                                 "dependencies. Can be specified more than "
                                 "once. If not specified then stacker will "
                                 "work on all stacks in the config file.")
        parser.add_argument("-j", "--max-parallel", action="store", type=int,
                            default=0,
                            help="The maximum number of stacks to execute in "
                                 "parallel. If not provided, the value will "
                                 "be constrained based on the underlying "
                                 "graph.")
        parser.add_argument("-t", "--tail", action="store_true",
                            help="Tail the CloudFormation logs while working "
                                 "with stacks")
        parser.add_argument("-d", "--dump", action="store", type=str,
                            help="Dump the rendered Cloudformation templates "
                                 "to a directory")

    def run(self, options, **kwargs):
        super(Build, self).run(options, **kwargs)
        action = build.Action(options.context,
                              provider_builder=options.provider_builder,
                              cancel=cancel())
        action.execute(concurrency=options.max_parallel,
                       outline=options.outline,
                       tail=options.tail,
                       dump=options.dump)

    def get_context_kwargs(self, options, **kwargs):
        return {"stack_names": options.stacks, "force_stacks": options.force}
