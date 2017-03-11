import logging

from .base import BaseAction
from ..exceptions import (
    StackDoesNotExist,
    DestoryWithoutNotificationQueue
)
from .. import util
from ..status import (
    CompleteStatus,
    SubmittedStatus,
    SkippedStatus
)
from ..plan import Plan

logger = logging.getLogger(__name__)

DestroyedStatus = CompleteStatus("stack destroyed")
DestroyingStatus = SubmittedStatus("submitted for destruction")


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
        if tail:
            plan_kwargs["watch_func"] = self.provider.tail_stack
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
            return SkippedStatus()

        if (('NotificationARNs' not in provider_stack) or
                (not provider_stack['NotificationARNs'])):
            raise DestoryWithoutNotificationQueue(stack.fqn)

        self.provider.set_listener_topic_arn(
            provider_stack['NotificationARNs'][0]
        )
        self.provider.destroy_stack(stack.fqn)
        return DestroyingStatus

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
