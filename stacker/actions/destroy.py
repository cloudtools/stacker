import logging

from .base import BaseAction
from ..exceptions import (
    StackDoesNotExist,
    DestroyWithoutNotificationQueue
)
from .. import util
from ..status import (
    SubmittedStatus,
    StackDoesNotExist as StackDoesNotExistStatus
)
from ..plan import Plan

logger = logging.getLogger(__name__)


class Action(BaseAction):

    """Responsible for destroying CloudFormation stacks.

    Generates a destruction plan based on stack dependencies. Stack
    dependencies are reversed from the build action. For example, if a Stack B
    requires Stack A during build, during destroy Stack A requires Stack B be
    destroyed first.

    The plan defaults to printing an outline of what will be destroyed. If
    forced to execute, each stack will get destroyed in order.

    """

    def _get_dependencies(self, stacks_dict):
        dependencies = {}
        for stack_name, stack in stacks_dict.iteritems():
            required_stacks = stack.requires
            if not required_stacks:
                if stack_name not in dependencies:
                    dependencies[stack_name] = required_stacks
                continue

            for requirement in required_stacks:
                dependencies.setdefault(requirement, set()).add(stack_name)
        return dependencies

    def _generate_plan(self, tail=False):
        plan_kwargs = {}
        plan = Plan(description="Destroy stacks",
                    poll_func=self.provider.poll_events,
                    **plan_kwargs)

        stacks_dict = self.context.get_stacks_dict()
        dependencies = self._get_dependencies(stacks_dict)
        for stack_name in self.get_stack_execution_order(dependencies):
            plan.add(
                stacks_dict[stack_name],
                run_func=self._destroy_stack,
                requires=dependencies.get(stack_name)
            )
        return plan

    def _destroy_stack(self, stack, **kwargs):
        logger.debug("Destroying stack: %s", stack.fqn)

        try:
            provider_stack = self.provider.get_stack(stack.fqn)
        except StackDoesNotExist:
            return StackDoesNotExistStatus('stack does not exist')

        if not provider_stack.get("NotificationARNs"):
            raise DestroyWithoutNotificationQueue(stack.fqn)

        self.provider.destroy_stack(stack.fqn)
        return SubmittedStatus("submitted for destruction")

    def pre_run(self, outline=False, *args, **kwargs):
        """Any steps that need to be taken prior to running the action."""
        pre_destroy = self.context.config.get("pre_destroy")
        if not outline and pre_destroy:
            util.handle_hooks(
                stage="pre_destroy",
                hooks=pre_destroy,
                provider=self.provider,
                context=self.context
            )

    def cleanup(self):
        """Cleans up any resources that do not need to exist after stacker
        has finished building all the stacks.

        This is specifically used when deleting the sqs queues used for
        polling events.

        """
        logger.debug('Cleaning up sqs queues')
        self.provider.cleanup()

    def run(self, force, tail=False, *args, **kwargs):
        plan = self._generate_plan(tail=tail)
        if force:
            # need to generate a new plan to log since the outline sets the
            # steps to COMPLETE in order to log them
            debug_plan = self._generate_plan()
            debug_plan.outline(logging.DEBUG)
            plan.execute()
        else:
            plan.outline(message="To execute this plan, run with \"--force\" "
                                 "flag.")

    def post_run(self, outline=False, *args, **kwargs):
        """Any steps that need to be taken after running the action."""
        post_destroy = self.context.config.get("post_destroy")
        if not outline and post_destroy:
            util.handle_hooks(
                stage="post_destroy",
                hooks=post_destroy,
                provider=self.provider,
                context=self.context)
