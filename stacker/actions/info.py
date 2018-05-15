import logging

from .base import BaseAction
from .. import exceptions

logger = logging.getLogger(__name__)


class Action(BaseAction):
    """Get information on CloudFormation stacks.

    Displays the outputs for the set of CloudFormation stacks.

    """

    def run(self, *args, **kwargs):
        logger.info('Outputs for stacks: %s', self.context.get_fqn())
        for stack in self.context.get_stacks():
            provider = self.build_provider(stack)

            try:
                provider_stack = provider.get_stack(stack.fqn)
            except exceptions.StackDoesNotExist:
                logger.info('Stack "%s" does not exist.' % (stack.fqn,))
                continue

            logger.info('%s:', stack.fqn)
            if 'Outputs' in provider_stack:
                for output in provider_stack['Outputs']:
                    logger.info(
                        '\t%s: %s',
                        output['OutputKey'],
                        output['OutputValue']
                    )
