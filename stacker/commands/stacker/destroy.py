"""Destroys CloudFormation stacks based on the given config.

Stacker will determine the order in which stacks should be destroyed based on
any manual requirements they specify or output values they rely on from other
stacks.

"""
from .base import BaseCommand
from ...actions import destroy


class Destroy(BaseCommand):

    name = "destroy"
    description = __doc__

    def add_arguments(self, parser):
        super(Destroy, self).add_arguments(parser)
        parser.add_argument('-f', '--force', action='store_true',
                            help="Whether or not you want to go through "
                                 " with destroying the stacks")
        parser.add_argument('-t', '--tail', action='store_true',
                            help='Tail the CloudFormation logs while working'
                                 'with stacks')

    def run(self, options, **kwargs):
        super(Destroy, self).run(options, **kwargs)
        action = destroy.Action(options.context, provider=options.provider)
        action.execute(force=options.force, tail=options.tail)
