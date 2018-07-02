"""Destroys CloudFormation stacks based on the given config.

Stacker will determine the order in which stacks should be destroyed based on
any manual requirements they specify or output values they rely on from other
stacks.

"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from .base import BaseCommand, cancel
from ...actions import destroy


class Destroy(BaseCommand):

    name = "destroy"
    description = __doc__

    def add_arguments(self, parser):
        super(Destroy, self).add_arguments(parser)
        parser.add_argument("-f", "--force", action="store_true",
                            help="Whether or not you want to go through "
                                 " with destroying the stacks")
        parser.add_argument("--stacks", action="append",
                            metavar="STACKNAME", type=str,
                            help="Only work on the stacks given. Can be "
                                 "specified more than once. If not specified "
                                 "then stacker will work on all stacks in the "
                                 "config file.")
        parser.add_argument("-j", "--max-parallel", action="store", type=int,
                            default=0,
                            help="The maximum number of stacks to execute in "
                                 "parallel. If not provided, the value will "
                                 "be constrained based on the underlying "
                                 "graph.")
        parser.add_argument("-t", "--tail", action="store_true",
                            help="Tail the CloudFormation logs while working "
                                 "with stacks")

    def run(self, options, **kwargs):
        super(Destroy, self).run(options, **kwargs)
        action = destroy.Action(options.context,
                                provider_builder=options.provider_builder,
                                cancel=cancel())
        action.execute(concurrency=options.max_parallel,
                       force=options.force,
                       tail=options.tail)

    def get_context_kwargs(self, options, **kwargs):
        return {"stack_names": options.stacks}
