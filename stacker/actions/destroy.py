import logging

from . import base
from ..plan import COMPLETE, PENDING, SKIPPED, Plan

logger = logging.getLogger(__name__)


class Action(base.BaseAction):

    def _get_dependencies(self, stacks_dict):
        dependencies = {}
        for stack_name, stack in stacks_dict.iteritems():
            provider_stack = self.provider.get_stack(stack.fqn)
            required_stacks = []
            if provider_stack:
                required_stacks = self.provider.get_required_stacks(provider_stack)

            if not required_stacks:
                if stack_name not in dependencies:
                    dependencies[stack_name] = required_stacks
                continue

            for requirement in required_stacks.split(':'):
                dependencies.setdefault(requirement, []).append(stack_name)
        return dependencies

    def _generate_plan(self):
        plan = Plan(details='Destroy stacks', provider=self.provider)
        stacks = self.context.get_stacks()

        stacks_dict = dict((stack.name, stack) for stack in stacks)
        dependencies = self._get_dependencies(stacks_dict)
        for stack_name in self.get_stack_execution_order(dependencies):
            plan.add(
                stacks_dict[stack_name],
                run_func=self._destroy_stack,
            )
        return plan

    def _destroy_stack(self, results, stack, **kwargs):
        provider_stack = self.provider.get_stack(stack.fqn)
        if not provider_stack:
            logger.debug("Stack %s does not exist.", stack.fqn)
            return SKIPPED

        logger.debug(
            "Stack %s provider status: %s",
            self.provider.get_stack_name(provider_stack),
            self.provider.get_stack_status(provider_stack),
        )
        if self.provider.is_stack_destroyed(provider_stack):
            return COMPLETE
        elif self.provider.is_stack_in_progress(provider_stack):
            return PENDING
        else:
            self.provider.destroy_stack(provider_stack)

    def run(self, force, *args, **kwargs):
        plan = self._generate_plan()
        if force:
            plan.execute()
        else:
            plan.outline()
