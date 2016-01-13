import logging

from .. import exceptions
from ..plan import COMPLETE, SKIPPED, Plan
from . import build
import difflib
import json
import sys

logger = logging.getLogger(__name__)


class Action(build.Action):
    """ Responsible for diff'ing CF stacks in AWS and on disk

    Generates the build plan based on stack dependencies (these dependencies
    are determined automatically based on references to output values from
    other stacks).

    The plan is then used to pull the current CloudFormation template from
    AWS and compare it to the generated templated based on the current
    config.
    """

    def _normalize_json(self, json_str):
        """Takes a string representing a JSON object and normalizes it"""
        obj = json.loads(json_str)
        json_str = json.dumps(obj, sort_keys=True, indent=4)
        lines = json_str.split("\n")
        result = []
        for line in lines:
            result.append(line + "\n")
        return result

    def _diff_stack(self, stack, **kwargs):
        """Handles the diffing a stack in CloudFormation vs our config"""
        if not build.should_submit(stack) or not build.should_update(stack):
            return SKIPPED

        try:
            old_stack = self.provider.get_template(stack.fqn)
        except exceptions.StackDoesNotExist:
            old_stack = None

        new_stack = self._normalize_json(stack.blueprint.rendered)
        logger.info("============== Stack: %s ==============", stack)
        if not old_stack:
            logger.info("New template contents:")
            sys.stdout.write(''.join(new_stack))
        else:
            old_stack = self._normalize_json(old_stack)
            count = 0
            lines = difflib.context_diff(
                old_stack, new_stack,
                fromfile="old_stack", tofile="new_stack")

            for line in lines:
                sys.stdout.write(line)
                count += 1
            if not count:
                print "*** No changes ***"
                return SKIPPED
        return COMPLETE

    def _generate_plan(self):
        plan_kwargs = {}
        plan = Plan(description='Create/Update stacks', **plan_kwargs)
        stacks = self.context.get_stacks_dict()
        dependencies = self._get_dependencies()
        for stack_name in self.get_stack_execution_order(dependencies):
            plan.add(
                stacks[stack_name],
                run_func=self._diff_stack,
                requires=dependencies.get(stack_name),
            )
        return plan

    def run(self, *args, **kwargs):
        plan = self._generate_plan()
        debug_plan = self._generate_plan()
        debug_plan.outline(logging.DEBUG)
        logger.info("Diffing stacks: %s", ', '.join(plan.keys()))
        plan.execute()
