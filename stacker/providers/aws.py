import logging

import boto
from boto import cloudformation

from . import exceptions
from .base import BaseProvider

logger = logging.getLogger(__name__)


class Provider(BaseProvider):

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

    @property
    def cloudformation(self):
        if not hasattr(self, '_cloudformation'):
            self._cloudformation = cloudformation.connect_to_region(self.region)
        return self._cloudformation

    def get_stack(self, stack_name, **kwargs):
        stack = None
        try:
            stack = self.cloudformation.describe_stacks(stack_name)[0]
        except boto.exception.BotoServerError as e:
            if 'does not exist' not in e.message:
                raise
        return stack

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
        self.cloudformation.delete_stack(stack.stack_id)
        return True

    def create_stack(self, fqn, template_url, parameters, tags, **kwargs):
        logger.info("Stack %s not found, creating.", fqn)
        logger.debug("Using parameters: %s", parameters)
        logger.debug("Using tags: %s", tags)
        self.cloudformation.create_stack(
            fqn,
            template_url=template_url,
            parameters=parameters, tags=tags,
            capabilities=['CAPABILITY_IAM'],
        )
        return True

    def update_stack(self, fqn, template_url, parameters, tags, **kwargs):
        try:
            logger.info("Attempting to update stack %s.", fqn)
            self.cloudformation.update_stack(
                fqn,
                template_url=template_url,
                parameters=parameters,
                tags=tags,
                capabilities=['CAPABILITY_IAM'],
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

    def get_required_stacks(self, stack, **kwargs):
        required_stacks = []
        if 'required_stacks' in stack.tags:
            required_stacks = stack.tags['required_stacks']
        return required_stacks

    def get_stack_name(self, stack, **kwargs):
        return stack.stack_name
