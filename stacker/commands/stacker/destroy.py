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
                            help="Whehter or not you want to go through "
                                 " with destroying the stacks")

    def run(self, options, **kwargs):
        super(Destroy, self).run(options, **kwargs)
        action = destroy.Action(options.context, provider=options.provider)
        stack_names = ['  - %s' % (s.fqn,) for s in options.context.get_stacks()]
        message = '\nAre you sure you want to destroy the following stacks:\n%s\n\n(yes/no): ' % (
            '\n'.join(stack_names),
        )
        force = False
        if options.force:
            confirm = raw_input(message)
            force = confirm.lower() == 'yes'
            if not force:
                self.logger.info('Confirmation failed, printing ouline...')
        action.execute(force=force)
