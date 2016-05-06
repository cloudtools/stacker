import logging

from .base import BaseAction
from .. import exceptions, util
from ..exceptions import StackDidNotChange
from ..plan import SUBMITTED, Plan
from ..status import (
    NotSubmittedStatus,
    NotUpdatedStatus,
    DidNotChangeStatus,
    SubmittedStatus,
    CompleteStatus
)


logger = logging.getLogger(__name__)


def should_update(stack):
    """Tests whether a stack should be submitted for updates to CF.

    Args:
        stack (:class:`stacker.stack.Stack`): The stack object to check.

    Returns:
        bool: If the stack should be updated, return True.
    """
    if stack.locked:
        if not stack.force:
            logger.info("Stack %s locked and not in --force list. "
                        "Refusing to update.", stack.name)
            return False
        else:
            logger.debug("Stack %s locked, but is in --force "
                         "list.", stack.name)
    return True


def should_submit(stack):
    """Tests whether a stack should be submitted to CF for update/create

    Args:
        stack (:class:`stacker.stack.Stack`): The stack object to check.

    Returns:
        bool: If the stack should be submitted, return True.
    """
    if stack.enabled:
        return True

    logger.info("Stack %s is not enabled.  Skipping.", stack.name)
    return False


def resolve_parameters(parameters, blueprint, context, provider):
    """Resolves parameters for a given blueprint.

    Given a list of parameters, first discard any parameters that the
    blueprint does not use. Then, if a parameter is a list of outputs
    in the format of <stack_name>::<output_name>,... pull those output(s)
    from the foreign stack(s).

    Args:
        parameters (dict): A dictionary of parameters provided by the
            stack definition
        blueprint (:class:`stacker.blueprint.base.Blueprint`): A Blueprint
            object that is having the parameters applied to it.
        context (:class:`stacker.context.Context`): The context object used
            to get the FQN of stacks.
        provider (:class:`stacker.providers.base.BaseProvider`): The provider
            used for looking up stacks & their outputs.

    Returns:
        dict: The resolved parameters.

    """
    params = {}
    blueprint_params = blueprint.parameters
    for k, v in parameters.items():
        if k not in blueprint_params:
            logger.debug("Template %s does not use parameter %s.",
                         blueprint.name, k)
            continue
        value = v
        if isinstance(value, basestring) and '::' in value:
            # Get from the Output(s) of another stack(s) in the stack_map
            v_list = []
            values = value.split(',')
            for v in values:
                stack_name, output = v.split('::')
                stack_fqn = context.get_fqn(stack_name)
                try:
                    v_list.append(
                        provider.get_output(stack_fqn, output))
                except KeyError:
                    raise exceptions.OutputDoesNotExist(stack_fqn, v)
            value = ','.join(v_list)
        if value is None:
            logger.debug("Got None value for parameter %s, not submitting it "
                         "to cloudformation, default value should be used.",
                         k)
            continue
        if isinstance(value, bool):
            logger.debug("Converting parameter %s boolean '%s' to string.",
                         k, value)
            value = str(value).lower()
        params[k] = value
    return params


class Action(BaseAction):
    """Responsible for building & coordinating CloudFormation stacks.

    Generates the build plan based on stack dependencies (these dependencies
    are determined automatically based on references to output values from
    other stacks).

    The plan can then either be printed out as an outline or executed. If
    executed, each stack will get launched in order which entails:
        - Pushing the generated CloudFormation template to S3 if it has changed
        - Submitting either a build or update of the given stack to the
          `Provider`.
        - Stores the stack outputs for reference by other stacks.

    """

    def _resolve_parameters(self, parameters, blueprint):
        """Resolves parameters for a given blueprint.

        Given a list of parameters, first discard any parameters that the
        blueprint does not use. Then, if a parameter is a list of outputs
        in the format of <stack_name>::<output_name>,... pull those output(s)
        from the foreign stack(s).

        Args:
            parameters (dict): A dictionary of parameters provided by the
                stack definition
            blueprint (:class:`stacker.blueprint.base.Blueprint`): A Blueprint
                object that is having the parameters applied to it.

        Returns:
            dict: The resolved parameters.

        """
        return resolve_parameters(parameters, blueprint, self.context,
                                  self.provider)

    def build_parameters(self, stack, provider_stack=None):
        """Builds the parameters for our stack

        Args:
            stack (:class:`cloudformation.stack`): A Cloudformation stack
            provider_stack (:class:`stacker.providers.base.Provider`): An
                optional Stacker provider object

        Returns:
            dict: The parameters for the given stack
        """
        parameters = self._resolve_parameters(stack.parameters,
                                              stack.blueprint)
        required_params = [k for k, v in stack.blueprint.required_parameters]
        parameters = self._handle_missing_parameters(parameters,
                                                     required_params,
                                                     provider_stack)
        return parameters

    def _build_stack_tags(self, stack):
        """Builds a common set of tags to attach to a stack"""
        tags = {
            'stacker_namespace': self.context.namespace,
        }
        return tags

    def _launch_stack(self, stack, **kwargs):
        """Handles the creating or updating of a stack in CloudFormation.

        Also makes sure that we don't try to create or update a stack while
        it is already updating or creating.

        """
        if not should_submit(stack):
            return NotSubmittedStatus()

        try:
            provider_stack = self.provider.get_stack(stack.fqn)
        except exceptions.StackDoesNotExist:
            provider_stack = None

        old_status = kwargs.get("status")
        if provider_stack and old_status == SUBMITTED:
            logger.debug(
                "Stack %s provider status: %s",
                stack.fqn,
                self.provider.get_stack_status(provider_stack),
            )
            if self.provider.is_stack_completed(provider_stack):
                submit_reason = getattr(old_status, "reason", None)
                return CompleteStatus(submit_reason)
            elif self.provider.is_stack_in_progress(provider_stack):
                logger.debug("Stack %s in progress.", stack.fqn)
                return old_status

        logger.debug("Launching stack %s now.", stack.fqn)
        template_url = self.s3_stack_push(stack.blueprint)
        tags = self._build_stack_tags(stack)
        parameters = self.build_parameters(stack, provider_stack)

        new_status = None

        if not provider_stack:
            new_status = SubmittedStatus("creating new stack")
            logger.info("Creating new stack: %s", stack.fqn)
            self.provider.create_stack(stack.fqn, template_url, parameters,
                                       tags)
        else:
            if not should_update(stack):
                return NotUpdatedStatus()
            try:
                new_status = SubmittedStatus("updating existing stack")
                self.provider.update_stack(stack.fqn, template_url, parameters,
                                           tags)
                logger.info("Updating existing stack: %s", stack.fqn)
            except StackDidNotChange:
                return DidNotChangeStatus()

        return new_status

    def _handle_missing_parameters(self, params, required_params,
                                   existing_stack=None):
        """Handles any missing parameters.

        If an existing_stack is provided, look up missing parameters there.

        Args:
            params (dict): key/value dictionary of stack definition parameters
            required_params (list): A list of required parameter names.
            existing_stack (`boto.cloudformation.stack.Stack`): A `Stack`
                object. If provided, will be searched for any missing
                parameters.

        Returns:
            list of tuples: The final list of key/value pairs returned as a
                list of tuples.

        Raises:
            MissingParameterException: Raised if a required parameter is
                still missing.

        """
        missing_params = list(set(required_params) - set(params.keys()))
        if existing_stack:
            stack_params = {p.key: p.value for p in existing_stack.parameters}
            for p in missing_params:
                if p in stack_params:
                    value = stack_params[p]
                    logger.debug("Using parameter %s from existing stack: %s",
                                 p, value)
                    params[p] = value
        final_missing = list(set(required_params) - set(params.keys()))
        if final_missing:
            raise exceptions.MissingParameterException(final_missing)

        return params.items()

    def _generate_plan(self, tail=False):
        plan_kwargs = {}
        if tail:
            plan_kwargs['watch_func'] = self.provider.tail_stack
        plan = Plan(description='Create/Update stacks', **plan_kwargs)
        stacks = self.context.get_stacks_dict()
        dependencies = self._get_dependencies()
        for stack_name in self.get_stack_execution_order(dependencies):
            plan.add(
                stacks[stack_name],
                run_func=self._launch_stack,
                requires=dependencies.get(stack_name),
            )
        return plan

    def _get_dependencies(self):
        dependencies = {}
        for stack in self.context.get_stacks():
            dependencies[stack.fqn] = stack.requires
        return dependencies

    def pre_run(self, outline=False, *args, **kwargs):
        """Any steps that need to be taken prior to running the action."""
        pre_build = self.context.config.get('pre_build')
        if not outline and pre_build:
            util.handle_hooks('pre_build', pre_build, self.provider.region,
                              self.context)

    def run(self, outline=False, tail=False, *args, **kwargs):
        """Kicks off the build/update of the stacks in the stack_definitions.

        This is the main entry point for the Builder.

        """
        plan = self._generate_plan(tail=tail)
        if not outline:
            # need to generate a new plan to log since the outline sets the
            # steps to COMPLETE in order to log them
            debug_plan = self._generate_plan()
            debug_plan.outline(logging.DEBUG)
            logger.info("Launching stacks: %s", ', '.join(plan.keys()))
            plan.execute()
        else:
            plan.outline()

    def post_run(self, outline=False, *args, **kwargs):
        """Any steps that need to be taken after running the action."""
        post_build = self.context.config.get('post_build')
        if not outline and post_build:
            util.handle_hooks('post_build', post_build, self.provider.region,
                              self.context)
