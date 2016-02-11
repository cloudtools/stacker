import logging

from .. import exceptions
from ..plan import COMPLETE, Plan
from ..status import NotSubmittedStatus, NotUpdatedStatus
from . import build
import difflib
import json

logger = logging.getLogger(__name__)


def diff_dictionaries(old_dict, new_dict):
    """Diffs two single dimension dictionaries

    Returns the number of changes and an unordered list
    expressing the common entries and changes.

    Args:
        old_dict(dict): old dictionary
        new_dict(dict): new dictionary

    Returns: list()
        int: number of changed records
        list: [str(<change type>), <key>, <value>]

        Where <change type>: +, - or <space>
    """

    old_set = set(old_dict)
    new_set = set(new_dict)

    added_set = new_set - old_set
    removed_set = old_set - new_set
    common_set = old_set & new_set

    changes = 0
    output = []
    for key in added_set:
        changes += 1
        output.append(['+', key, new_dict[key]])

    for key in removed_set:
        changes += 1
        output.append(['-', key, old_dict[key]])

    for key in common_set:
        if str(old_dict[key]) != str(new_dict[key]):
            changes += 1
            output.append(['-', key, old_dict[key]])
            output.append(['+', key, new_dict[key]])
        else:
            output.append([' ', key, new_dict[key]])

    return [changes, output]


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
        """Compares the old vs. new parameters and prints a 'diff'

        If there are no changes, we print nothing.

        Args:
            old_params(dict): old paramters
            new_params(dict): new parameters
        """
        [changes, diff] = diff_dictionaries(old_params, new_params)
        if changes == 0:
            return

        print """--- Old Parameters
+++ New Parameters
******************"""

        for line in diff:
            print "%s%s = %s" % (line[0], line[1], line[2])

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

    def _print_new_stack(self, stack, parameters):
        """Prints out the parameters & stack contents of a new stack"""
        print "New template parameters:"
        for param in sorted(parameters, key=lambda param: param[0]):
            print "%s = %s" % (param[0], param[1])

        print "\nNew template contents:"
        print "".join(stack)

    def _print_stack_changes(self, stack_name, new_stack, old_stack,
                             new_params, old_params):
        """Prints out the paramters (if changed) and stack diff"""
        from_file = "old_%s" % (stack_name,)
        to_file = "new_%s" % (stack_name,)
        lines = difflib.context_diff(
            old_stack, new_stack,
            fromfile=from_file, tofile=to_file)

        template_changes = list(lines)
        if not template_changes:
            print "*** No changes to template ***"
        else:
            self._diff_parameters(old_params, new_params)
            print "".join(template_changes)

    def _diff_stack(self, stack, **kwargs):
        """Handles the diffing a stack in CloudFormation vs our config"""
        if not build.should_submit(stack):
            return NotSubmittedStatus()

        if not build.should_update(stack):
            return NotUpdatedStatus()

        # get the current stack template & params from AWS
        try:
            [old_template, old_params] = self.provider.get_stack_info(
                stack.fqn)
        except exceptions.StackDoesNotExist:
            old_template = None
            old_params = {}

        # generate our own template & params
        new_template = stack.blueprint.rendered
        parameters = self.build_parameters(stack)
        new_params = dict()
        for p in parameters:
            new_params[p[0]] = p[1]
        new_stack = self._normalize_json(new_template)

        print "============== Stack: %s ==============" % (stack.name,)
        # If this is a completely new template dump our params & stack
        if not old_template:
            self._print_new_stack(new_stack, parameters)
        else:
            # Diff our old & new stack/parameters
            old_stack = self._normalize_json(old_template)
            self._print_stack_changes(stack.name, new_stack, old_stack,
                                      new_params, old_params)
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

    """Don't ever do anything for pre_run or post_run"""
    def pre_run(self, *args, **kwargs):
        pass

    def post_run(self, *args, **kwargs):
        pass
