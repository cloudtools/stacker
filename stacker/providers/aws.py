import logging

import boto
from boto import cloudformation

from .. import exceptions
from .base import BaseProvider
from ..util import retry_with_backoff

logger = logging.getLogger(__name__)


def get_output_dict(stack):
    """Returns a dict of key/values for the outputs for a given CF stack.

    Args:
        stack (boto.cloudformation.stack.Stack): The stack object to get
            outputs from.

    Returns:
        dict: A dictionary with key/values for each output on the stack.

    """
    outputs = {}
    for output in stack.outputs:
        logger.debug("    %s %s: %s", stack.stack_name, output.key,
                     output.value)
        outputs[output.key] = output.value
    return outputs


def retry_on_throttling(fn, attempts=3, args=None, kwargs=None):
    """Wrap retry_with_backoff to handle AWS Cloudformation Throttling.

    Args:
        fn (function): The function to call.
        attempts (int): Maximum # of attempts to retry the function.
        args (list): List of positional arguments to pass to the function.
        kwargs (dict): Dict of keyword arguments to pass to the function.

    Returns:
        passthrough: This returns the result of the function call itself.

    Raises:
        passthrough: This raises any exceptions the function call raises,
            except for boto.exception.BotoServerError, provided it doesn't
            retry more than attempts.
    """
    def _throttling_checker(exc):
        if exc.status == 400 and exc.error_code == "Throttling":
            logger.debug("AWS throttling calls.")
            return True
        return False

    return retry_with_backoff(fn, args=args, kwargs=kwargs, attempts=attempts,
                              exc_list=(boto.exception.BotoServerError, ),
                              retry_checker=_throttling_checker)


class Provider(BaseProvider):
    """AWS CloudFormation Provider"""

    DELETED_STATUS = 'DELETE_COMPLETE'
    IN_PROGRESS_STATUSES = (
        'CREATE_IN_PROGRESS',
        'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
        'UPDATE_IN_PROGRESS',
        'DELETE_IN_PROGRESS',
    )
    COMPLETE_STATUSES = (
        'CREATE_COMPLETE',
        'UPDATE_COMPLETE',
    )

    def __init__(self, region, **kwargs):
        self.region = region
        self._outputs = {}

    @property
    def cloudformation(self):
        if not hasattr(self, '_cloudformation'):
            self._cloudformation = cloudformation.connect_to_region(
                self.region)
        return self._cloudformation

    def get_stack(self, stack_name, **kwargs):
        try:
            return retry_on_throttling(self.cloudformation.describe_stacks,
                                       args=[stack_name])[0]
        except boto.exception.BotoServerError as e:
            if 'does not exist' not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

    def get_stack_status(self, stack, **kwargs):
        return stack.stack_status

    def is_stack_completed(self, stack, **kwargs):
        return stack.stack_status in self.COMPLETE_STATUSES

    def is_stack_in_progress(self, stack, **kwargs):
        return stack.stack_status in self.IN_PROGRESS_STATUSES

    def is_stack_destroyed(self, stack, **kwargs):
        return stack.stack_status == self.DELETED_STATUS

    def destroy_stack(self, stack, **kwargs):
        logger.info("Destroying stack: %s" % (stack.stack_name,))
        retry_on_throttling(self.cloudformation.delete_stack,
                            args=[stack.stack_id])
        return True

    def create_stack(self, fqn, template_url, parameters, tags, **kwargs):
        logger.info("Stack %s not found, creating.", fqn)
        logger.debug("Using parameters: %s", parameters)
        logger.debug("Using tags: %s", tags)
        retry_on_throttling(
            self.cloudformation.create_stack,
            args=[fqn],
            kwargs=dict(template_url=template_url,
                        parameters=parameters, tags=tags,
                        capabilities=['CAPABILITY_IAM']),
        )
        return True

    def update_stack(self, fqn, template_url, parameters, tags, **kwargs):
        try:
            logger.info("Attempting to update stack %s.", fqn)
            retry_on_throttling(
                self.cloudformation.update_stack,
                args=[fqn],
                kwargs=dict(template_url=template_url,
                            parameters=parameters,
                            tags=tags,
                            capabilities=['CAPABILITY_IAM']),
            )
        except boto.exception.BotoServerError as e:
            if 'No updates are to be performed.' in e.message:
                logger.info(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            raise
        return True

    def get_stack_name(self, stack, **kwargs):
        return stack.stack_name

    def get_outputs(self, stack_name, *args, **kwargs):
        if stack_name not in self._outputs:
            stack = self.get_stack(stack_name)
            self._outputs[stack_name] = get_output_dict(stack)
        return self._outputs[stack_name]
