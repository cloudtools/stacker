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

    def _diff_parameters(self, old_params, new_params):
        """Compares the old vs. new parameters and returns a 'diff'

        Args:
            old_params(dict): old paramters
            new_params(dict): new parameters

        Returns:
            int: number of changed entries
            string: "diff" of all parameters and how they changed
        """
        output = []
        count = 0
        for k, v in old_params.iteritems():
            new_val = new_params.get(k, "_Undef_")
            if str(v) != str(new_val):
                output.append("CHANGED   %s: %s => %s\n" % (k, v, new_val))
                count += 1
            else:
                output.append("NO CHANGE %s: %s\n" % (k, v))

        for k, v in new_params.iteritems():
            if not k in old_params:
                output.append("NEW       %s: %s\n" % (k, v))
                count += 1

        return [count, "".join(output)]

    def _normalize_json(self, template):
        """Normalizes our template for diffing

        Args:
            template(str): json string representing the template

        Returns:
            list: json representation of the parameters
        """
        obj = json.loads(template)
        json_str = json.dumps(obj, sort_keys=True, indent=4)
        result = []
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
            [old_template, old_params] = self.provider.get_stack_info(
                stack.fqn)
        except exceptions.StackDoesNotExist:
            old_template = None
            old_params = {}

        # generate our own template & params
        new_template = stack.blueprint.rendered
        resolved_parameters = self._resolve_parameters(stack.parameters,
                                                       stack.blueprint)
        required_params = [k for k, v in stack.blueprint.required_parameters]
        parameters = self._handle_missing_parameters(resolved_parameters,
                                                     required_params)
        new_params = dict()
        for p in parameters:
            new_params[p[0]] = p[1]
        new_stack = self._normalize_json(new_template)
        [param_changes, param_diff] = self._diff_parameters(
            old_params, new_params)

        print "============== Stack: %s ==============" % (stack,)
        if not old_template:
            print "Input parameters:"
            print param_diff
            print "New template contents:"
            sys.stdout.write(''.join(new_stack))
        else:
            old_stack = self._normalize_json(old_template)

            lines = difflib.context_diff(
                old_stack, new_stack,
                fromfile="old_stack", tofile="new_stack")

            count = 0
            # lines is a generator, not a list hence this is a bit fugly
            for line in lines:
                if count == 0:
                    print "Input parameters:"
                    print param_diff

                sys.stdout.write(line)
                count += 1

            if count == 0:
                print "*** No changes to template ***"
                return SKIPPED
            elif param_changes:
                print "Input parameters:"
                print param_diff

        return COMPLETE

    def _generate_plan(self):
        plan = Plan(description='Diff stacks')
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
