# TODO make this relevant
"""Destroy stacker
"""
from ..base import BaseCommand
from ...actions import destroy


class Destroy(BaseCommand):

    name = "destroy"
    description = __doc__

    def add_arguments(self, parser):
        super(Destroy, self).add_arguments(parser)
        parser.add_argument('-f', '--force', action='store_true',
                            help="Whehter or not you want to go through "
                                 " with destroying the stacks")

    def run(self, args, **kwargs):
        super(Destroy, self).run(args, **kwargs)
        action = destroy.Action(args.context, provider=args.provider)
        action.run(force=args.force)
