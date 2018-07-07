""" Diffs the config against the currently running CloudFormation stacks

Sometimes small changes can have big impacts.  Run "stacker diff" before
"stacker build" to detect bad things(tm) from happening in advance!
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from .base import BaseCommand
from ...actions import diff


class Diff(BaseCommand):
    name = "diff"
    description = __doc__

    def add_arguments(self, parser):
        super(Diff, self).add_arguments(parser)
        parser.add_argument("--force", action="append", default=[],
                            metavar="STACKNAME", type=str,
                            help="If a stackname is provided to --force, it "
                                 "will be diffed, even if it is locked in "
                                 "the config.")
        parser.add_argument("--stacks", action="append",
                            metavar="STACKNAME", type=str,
                            help="Only work on the stacks given. Can be "
                                 "specified more than once. If not specified "
                                 "then stacker will work on all stacks in the "
                                 "config file.")

    def run(self, options, **kwargs):
        super(Diff, self).run(options, **kwargs)
        action = diff.Action(options.context,
                             provider_builder=options.provider_builder)
        action.execute()

    def get_context_kwargs(self, options, **kwargs):
        return {"stack_names": options.stacks, "force_stacks": options.force}
