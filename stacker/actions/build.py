from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import logging

from .base import BaseAction, plan, build_walker
from .base import STACK_POLL_TIME

from ..providers.base import Template
from .. import util
from ..exceptions import (
    MissingParameterException,
    StackDidNotChange,
    StackDoesNotExist,
    CancelExecution,
)

from ..status import (
    NotSubmittedStatus,
    NotUpdatedStatus,
    DidNotChangeStatus,
    SubmittedStatus,
    CompleteStatus,
    FailedStatus,
    SkippedStatus,
    PENDING,
    WAITING,
    SUBMITTED,
    INTERRUPTED
)


logger = logging.getLogger(__name__)


def build_stack_tags(stack):
    """Builds a common set of tags to attach to a stack"""
    return [{'Key': t[0], 'Value': t[1]} for t in stack.tags.items()]


def should_update(stack):
    """Tests whether a stack should be submitted for updates to CF.

    Args:
        stack (:class:`stacker.stack.Stack`): The stack object to check.

    Returns:
        bool: If the stack should be updated, return True.

    """
    if stack.locked:
        if not stack.force:
            logger.debug("Stack %s locked and not in --force list. "
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

    logger.debug("Stack %s is not enabled.  Skipping.", stack.name)
    return False


def should_ensure_cfn_bucket(outline, dump):
    """Test whether access to the cloudformation template bucket is required

    Args:
        outline (bool): The outline action.
        dump (bool): The dump action.

    Returns:
        bool: If access to CF bucket is needed, return True.

    """
    return not outline and not dump


def _resolve_parameters(parameters, blueprint):
    """Resolves CloudFormation Parameters for a given blueprint.

    Given a list of parameters, handles:
        - discard any parameters that the blueprint does not use
        - discard any empty values
        - convert booleans to strings suitable for CloudFormation

    Args:
        parameters (dict): A dictionary of parameters provided by the
            stack definition
        blueprint (:class:`stacker.blueprint.base.Blueprint`): A Blueprint
            object that is having the parameters applied to it.

    Returns:
        dict: The resolved parameters.

    """
    params = {}
    param_defs = blueprint.get_parameter_definitions()

    for key, value in parameters.items():
        if key not in param_defs:
            logger.debug("Blueprint %s does not use parameter %s.",
                         blueprint.name, key)
            continue
        if value is None:
            logger.debug("Got None value for parameter %s, not submitting it "
                         "to cloudformation, default value should be used.",
                         key)
            continue
        if isinstance(value, bool):
            logger.debug("Converting parameter %s boolean \"%s\" to string.",
                         key, value)
            value = str(value).lower()
        params[key] = value
    return params


class UsePreviousParameterValue(object):
    """ A simple class used to indicate a Parameter should use it's existng
    value.
    """
    pass


def _handle_missing_parameters(parameter_values, all_params, required_params,
                               existing_stack=None):
    """Handles any missing parameters.

    If an existing_stack is provided, look up missing parameters there.

    Args:
        parameter_values (dict): key/value dictionary of stack definition
            parameters
        all_params (list): A list of all the parameters used by the
            template/blueprint.
        required_params (list): A list of all the parameters required by the
            template/blueprint.
        existing_stack (dict): A dict representation of the stack. If
            provided, will be searched for any missing parameters.

    Returns:
        list of tuples: The final list of key/value pairs returned as a
            list of tuples.

    Raises:
        MissingParameterException: Raised if a required parameter is
            still missing.

    """
    missing_params = list(set(all_params) - set(parameter_values.keys()))
    if existing_stack and 'Parameters' in existing_stack:
        stack_parameters = [
            p["ParameterKey"] for p in existing_stack["Parameters"]
        ]
        for p in missing_params:
            if p in stack_parameters:
                logger.debug(
                    "Using previous value for parameter %s from existing "
                    "stack",
                    p
                )
                parameter_values[p] = UsePreviousParameterValue
    final_missing = list(set(required_params) - set(parameter_values.keys()))
    if final_missing:
        raise MissingParameterException(final_missing)

    return list(parameter_values.items())


def handle_hooks(stage, hooks, provider, context, dump, outline):
    """Handle pre/post hooks.

    Args:
        stage (str): The name of the hook stage - pre_build/post_build.
        hooks (list): A list of dictionaries containing the hooks to execute.
        provider (:class:`stacker.provider.base.BaseProvider`): The provider
            the current stack is using.
        context (:class:`stacker.context.Context`): The current stacker
            context.
        dump (bool): Whether running with dump set or not.
        outline (bool): Whether running with outline set or not.

    """
    if not outline and not dump and hooks:
        util.handle_hooks(
            stage=stage,
            hooks=hooks,
            provider=provider,
            context=context
        )


class Action(BaseAction):
    """Responsible for building & coordinating CloudFormation stacks.

    Generates the build plan based on stack dependencies (these dependencies
    are determined automatically based on output lookups from other stacks).

    The plan can then either be printed out as an outline or executed. If
    executed, each stack will get launched in order which entails:

        - Pushing the generated CloudFormation template to S3 if it has changed
        - Submitting either a build or update of the given stack to the
            :class:`stacker.provider.base.Provider`.

    """

    def build_parameters(self, stack, provider_stack=None):
        """Builds the CloudFormation Parameters for our stack.

        Args:
            stack (:class:`stacker.stack.Stack`): A stacker stack
            provider_stack (dict): An optional Stacker provider object

        Returns:
            dict: The parameters for the given stack

        """
        resolved = _resolve_parameters(stack.parameter_values, stack.blueprint)
        required_parameters = list(stack.required_parameter_definitions)
        all_parameters = list(stack.all_parameter_definitions)
        parameters = _handle_missing_parameters(resolved, all_parameters,
                                                required_parameters,
                                                provider_stack)

        param_list = []

        for key, value in parameters:
            param_dict = {"ParameterKey": key}
            if value is UsePreviousParameterValue:
                param_dict["UsePreviousValue"] = True
            else:
                param_dict["ParameterValue"] = str(value)

            param_list.append(param_dict)

        return param_list

    def _launch_stack(self, stack, **kwargs):
        """Handles the creating or updating of a stack in CloudFormation.

        Also makes sure that we don't try to create or update a stack while
        it is already updating or creating.

        """
        old_status = kwargs.get("status")
        wait_time = 0 if old_status is PENDING else STACK_POLL_TIME
        if self.cancel.wait(wait_time):
            return INTERRUPTED

        if not should_submit(stack):
            return NotSubmittedStatus()

        provider = self.build_provider(stack)

        try:
            provider_stack = provider.get_stack(stack.fqn)
        except StackDoesNotExist:
            provider_stack = None

        if provider_stack and not should_update(stack):
            stack.set_outputs(
                self.provider.get_output_dict(provider_stack))
            return NotUpdatedStatus()

        recreate = False
        if provider_stack and old_status == SUBMITTED:
            logger.debug(
                "Stack %s provider status: %s",
                stack.fqn,
                provider.get_stack_status(provider_stack),
            )

            if provider.is_stack_rolling_back(provider_stack):
                if 'rolling back' in old_status.reason:
                    return old_status

                logger.debug("Stack %s entered a roll back", stack.fqn)
                if 'updating' in old_status.reason:
                    reason = 'rolling back update'
                else:
                    reason = 'rolling back new stack'

                return SubmittedStatus(reason)
            elif provider.is_stack_in_progress(provider_stack):
                logger.debug("Stack %s in progress.", stack.fqn)
                return old_status
            elif provider.is_stack_destroyed(provider_stack):
                logger.debug("Stack %s finished deleting", stack.fqn)
                recreate = True
                # Continue with creation afterwards
            # Failure must be checked *before* completion, as both will be true
            # when completing a rollback, and we don't want to consider it as
            # a successful update.
            elif provider.is_stack_failed(provider_stack):
                reason = old_status.reason
                if 'rolling' in reason:
                    reason = reason.replace('rolling', 'rolled')
                status_reason = provider.get_rollback_status_reason(stack.fqn)
                logger.info(
                    "%s Stack Roll Back Reason: " + status_reason, stack.fqn)
                return FailedStatus(reason)

            elif provider.is_stack_completed(provider_stack):
                stack.set_outputs(
                    provider.get_output_dict(provider_stack))
                return CompleteStatus(old_status.reason)
            else:
                return old_status

        logger.debug("Resolving stack %s", stack.fqn)
        stack.resolve(self.context, self.provider)

        logger.debug("Launching stack %s now.", stack.fqn)
        template = self._template(stack.blueprint)
        stack_policy = self._stack_policy(stack)
        tags = build_stack_tags(stack)
        parameters = self.build_parameters(stack, provider_stack)
        force_change_set = stack.blueprint.requires_change_set

        if recreate:
            logger.debug("Re-creating stack: %s", stack.fqn)
            provider.create_stack(stack.fqn, template, parameters,
                                  tags, stack_policy=stack_policy)
            return SubmittedStatus("re-creating stack")
        elif not provider_stack:
            logger.debug("Creating new stack: %s", stack.fqn)
            provider.create_stack(stack.fqn, template, parameters, tags,
                                  force_change_set,
                                  stack_policy=stack_policy)
            return SubmittedStatus("creating new stack")

        try:
            wait = stack.in_progress_behavior == "wait"
            if wait and provider.is_stack_in_progress(provider_stack):
                return WAITING
            if provider.prepare_stack_for_update(provider_stack, tags):
                existing_params = provider_stack.get('Parameters', [])
                provider.update_stack(
                    stack.fqn,
                    template,
                    existing_params,
                    parameters,
                    tags,
                    force_interactive=stack.protected,
                    force_change_set=force_change_set,
                    stack_policy=stack_policy,
                )

                logger.debug("Updating existing stack: %s", stack.fqn)
                return SubmittedStatus("updating existing stack")
            else:
                return SubmittedStatus("destroying stack for re-creation")
        except CancelExecution:
            stack.set_outputs(provider.get_output_dict(provider_stack))
            return SkippedStatus(reason="canceled execution")
        except StackDidNotChange:
            stack.set_outputs(provider.get_output_dict(provider_stack))
            return DidNotChangeStatus()

    def _template(self, blueprint):
        """Generates a suitable template based on whether or not an S3 bucket
        is set.

        If an S3 bucket is set, then the template will be uploaded to S3 first,
        and CreateStack/UpdateStack operations will use the uploaded template.
        If not bucket is set, then the template will be inlined.
        """
        if self.bucket_name:
            return Template(url=self.s3_stack_push(blueprint))
        else:
            return Template(body=blueprint.rendered)

    def _stack_policy(self, stack):
        """Returns a Template object for the stacks stack policy, or None if
        the stack doesn't have a stack policy."""
        if stack.stack_policy:
            return Template(body=stack.stack_policy)

    def _generate_plan(self, tail=False):
        return plan(
            description="Create/Update stacks",
            stack_action=self._launch_stack,
            tail=self._tail_stack if tail else None,
            context=self.context)

    def pre_run(self, outline=False, dump=False, *args, **kwargs):
        """Any steps that need to be taken prior to running the action."""
        if should_ensure_cfn_bucket(outline, dump):
            self.ensure_cfn_bucket()
        hooks = self.context.config.pre_build
        handle_hooks(
            "pre_build",
            hooks,
            self.provider,
            self.context,
            dump,
            outline
        )

    def run(self, concurrency=0, outline=False,
            tail=False, dump=False, *args, **kwargs):
        """Kicks off the build/update of the stacks in the stack_definitions.

        This is the main entry point for the Builder.

        """
        plan = self._generate_plan(tail=tail)
        if not plan.keys():
            logger.warn('WARNING: No stacks detected (error in config?)')
        if not outline and not dump:
            plan.outline(logging.DEBUG)
            logger.debug("Launching stacks: %s", ", ".join(plan.keys()))
            walker = build_walker(concurrency)
            plan.execute(walker)
        else:
            if outline:
                plan.outline()
            if dump:
                plan.dump(directory=dump, context=self.context,
                          provider=self.provider)

    def post_run(self, outline=False, dump=False, *args, **kwargs):
        """Any steps that need to be taken after running the action."""
        hooks = self.context.config.post_build
        handle_hooks(
            "post_build",
            hooks,
            self.provider,
            self.context,
            dump,
            outline
        )
