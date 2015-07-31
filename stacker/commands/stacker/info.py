"""Gets information on the CloudFormation stacks based on the given config."""

from .base import StackerCommand
from ...actions import info


class Info(StackerCommand):

    name = 'info'
    description = __doc__

    def run(self, options, **kwargs):
        super(Info, self).run(options, **kwargs)
        action = info.Action(options.context, provider=options.provider)
        action.execute()
