import logging

from .base import BaseAction, check_point_fn, outline_plan
from ..exceptions import StackDoesNotExist
from .. import util
from ..status import (
    CompleteStatus,
    SubmittedStatus,
    CancelledStatus,
    SUBMITTED,
)
from ..plan import Plan

from ..status import StackDoesNotExist as StackDoesNotExistStatus

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

    def _action(self, *args, **kwargs):
        return self._destroy_stack(*args, **kwargs)

    def _generate_plan(self, tail=False):
        return Plan(
            description="Destroy stacks",
            steps=self.steps,
            check_point=check_point_fn(),
            reverse=True)

    def _destroy_stack(self, step):
        stack = step.stack

        # Cancel execution if flag is set.
        if self.cancel.wait(0):
            return CancelledStatus(reason="cancelled")

        try:
            provider_stack = self.provider.get_stack(stack.fqn)
        except StackDoesNotExist:
            logger.debug("Stack %s does not exist.", stack.fqn)
            # Once the stack has been destroyed, it doesn't exist. If the
            # status of the step was SUBMITTED, we know we just deleted it,
            # otherwise it should be skipped
            if step.status == SUBMITTED:
                return DestroyedStatus
            else:
                return StackDoesNotExistStatus()

        logger.debug(
            "Stack %s provider status: %s",
            self.provider.get_stack_name(provider_stack),
            self.provider.get_stack_status(provider_stack),
        )
        if self.provider.is_stack_destroyed(provider_stack):
            return DestroyedStatus
        elif self.provider.is_stack_in_progress(provider_stack):
            return DestroyingStatus
        else:
            logger.debug("Destroying stack: %s", stack.fqn)
            self.provider.destroy_stack(provider_stack)
        return DestroyingStatus

    def pre_run(self, outline=False, *args, **kwargs):
        """Any steps that need to be taken prior to running the action."""
        pre_destroy = self.context.config.get("pre_destroy")
        if not outline and pre_destroy:
            util.handle_hooks(
                stage="pre_destroy",
                hooks=pre_destroy,
                provider=self.provider,
                context=self.context)

    def run(self, force, tail=False, semaphore=None, *args, **kwargs):
        plan = self._generate_plan(tail=tail)
        if force:
            outline_plan(plan, logging.DEBUG)
            plan.execute(semaphore=semaphore)
        else:
            outline_plan(
                plan,
                message="To execute this plan, run with \"--force\" flag.")

    def post_run(self, outline=False, *args, **kwargs):
        """Any steps that need to be taken after running the action."""
        post_destroy = self.context.config.get("post_destroy")
        if not outline and post_destroy:
            util.handle_hooks(
                stage="post_destroy",
                hooks=post_destroy,
                provider=self.provider,
                context=self.context)
