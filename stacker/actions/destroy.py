import logging

from .base import BaseAction
from ..exceptions import StackDoesNotExist
from ..plan import (
    COMPLETE,
    SKIPPED,
    SUBMITTED,
    Plan,
)

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

    def _generate_plan(self):
        plan = Plan(description='Destroy stacks')
        stacks_dict = self.context.get_stacks_dict()
        dependencies = self._get_dependencies(stacks_dict)
        for stack_name in self.get_stack_execution_order(dependencies):
            plan.add(
                stacks_dict[stack_name],
                run_func=self._destroy_stack,
                requires=dependencies.get(stack_name),
            )
        return plan

    def _destroy_stack(self, stack, **kwargs):
        try:
            provider_stack = self.provider.get_stack(stack.fqn)
        except StackDoesNotExist:
            logger.debug("Stack %s does not exist.", stack.fqn)
            # Once the stack has been destroyed, it doesn't exist. If the
            # status of the step was SUBMITTED, we know we just deleted it,
            # otherwise it should be skipped
            if kwargs.get('status', None) is SUBMITTED:
                return COMPLETE
            else:
                return SKIPPED

        logger.debug(
            "Stack %s provider status: %s",
            self.provider.get_stack_name(provider_stack),
            self.provider.get_stack_status(provider_stack),
        )
        if self.provider.is_stack_destroyed(provider_stack):
            return COMPLETE
        elif self.provider.is_stack_in_progress(provider_stack):
            return SUBMITTED
        else:
            self.provider.destroy_stack(provider_stack)
        return SUBMITTED

    def run(self, force, *args, **kwargs):
        plan = self._generate_plan()
        if force:
            # need to generate a new plan to log since the outline sets the
            # steps to COMPLETE in order to log them
            debug_plan = self._generate_plan()
            debug_plan.outline(logging.DEBUG)
            plan.execute()
        else:
            plan.outline(message='To execute this plan, run with "--force" '
                                 'flag.')
