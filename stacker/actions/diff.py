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

    def _normalize_json(self, json_str, parameters):
        """Normalizes our template & parameters for diffing

        Args:
            json_str(str): json string representing the template
            parameters(dict): parameters passed to the template

        Returns:
            list: json representation of the parameters & template
        """
        obj = json.loads(json_str)
        json_str = json.dumps(obj, sort_keys=True, indent=4)
        param_str = '"Parameters:" ' + \
            json.dumps(parameters, sort_keys=True, indent=4)
        result = []
        lines = param_str.split("\n")
        for line in lines:
            result.append(line + "\n")

        lines = json_str.split("\n")
        for line in lines:
            result.append(line + "\n")
        return result

    def _diff_stack(self, stack, **kwargs):
        """Handles the diffing a stack in CloudFormation vs our config"""
        if not build.should_submit(stack) or not build.should_update(stack):
            return SKIPPED

        # get the current stack template & params from AWS
        try:
            [old_template, old_params] = self.provider.get_stack_info(stack.fqn)
        except exceptions.StackDoesNotExist:
            old_template = None
            old_params = {}

        # generate our own template & params
        new_template = stack.blueprint.rendered
        parameters = self._resolve_parameters(stack.parameters,
                                              stack.blueprint)
        required_params = [k for k, v in stack.blueprint.required_parameters]
        parameters = self._handle_missing_parameters(parameters,
                                                     required_params)
        new_params = dict()
        for p in parameters:
            new_params[p[0]] = p[1]
        new_stack = self._normalize_json(new_template, new_params)

        logger.info("============== Stack: %s ==============", stack)
        if not old_template:
            logger.info("New template contents:")
            sys.stdout.write(''.join(new_stack))
        else:
            old_stack = self._normalize_json(old_template, old_params)
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
        plan = Plan(description='Diff stacks', **plan_kwargs)
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
