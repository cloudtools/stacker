import copy
import logging
import time

from aws_helper.connection import ConnectionManager
from boto.exception import BotoServerError, S3ResponseError

from .plan import (
    Plan, INPROGRESS_STATUSES, SUBMITTED, SKIPPED, PENDING, COMPLETE_STATUSES
)
from .util import get_bucket_location, load_object_from_string

logger = logging.getLogger(__name__)


class MissingParameterException(Exception):

    def __init__(self, parameters, *args, **kwargs):
        self.parameters = parameters
        message = 'Missing required parameters: %s' % (
            ', '.join(parameters),
        )
        super(MissingParameterException, self).__init__(message, *args,
                                                        **kwargs)


class ParameterDoesNotExist(Exception):

    def __init__(self, parameter, *args, **kwargs):
        message = 'Parameter: "%s" does not exist in output' % (parameter,)
        super(ParameterDoesNotExist, self).__init__(message, *args, **kwargs)


def get_stack_full_name(cfn_base, stack_name):
    return "%s-%s" % (cfn_base, stack_name)


def stack_template_key_name(blueprint):
    return "%s-%s.json" % (blueprint.name, blueprint.version)


def stack_template_url(bucket_name, blueprint):
    key_name = stack_template_key_name(blueprint)
    return "https://s3.amazonaws.com/%s/%s" % (bucket_name, key_name)


def gather_parameters(stack_def, builder_parameters):
    """ Merges builder provided & stack defined parameters.

    Ensures that more specificly defined parameters (ie: parameters defined
    specifically for the given stack: stack_name::parameter) override less
    specific parameters provided by the builder.

    Order of precedence:
        - builder defined stack specific (stack_name::parameter)
        - builder defined non-specific (parameter)
        - stack_def defined
    """
    parameters = copy.deepcopy(stack_def.get('parameters', {}))
    stack_specific_params = {}
    for key, value in builder_parameters.iteritems():
        stack = None
        if "::" in key:
            stack, key = key.split("::", 1)
        if not stack:
            # Non-stack specific, go ahead and add it
            parameters[key] = value
            continue
        # Gather stack specific params for later
        if stack == stack_def['name']:
            stack_specific_params[key] = value
    # Now update stack parameters with the stack specific parameters
    # ensuring they override generic parameters
    parameters.update(stack_specific_params)
    return parameters


def handle_missing_parameters(params, required_params, existing_stack=None):
    """ Handles any missing parameters.

    If an existing_stack is provided, look up missing parameters there.

    Args:
        params (dict): key/value dictionary of stack definition parameters
        required_params (list): A list of required parameter names.
        existing_stack (Stack): A boto.cloudformation.stack.Stack object.
                                If provided, will be searched for any
                                missing parameters.

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
        raise MissingParameterException(final_missing)

    return params.items()


class Builder(object):
    """ Responsible for building & coordinating CloudFormation stacks.

    Handles the conversion from:
        config -> Blueprints -> Cloudformation Templates

    Then pushes the templates into S3 if they have changed. Then kicks off
    the stacks in order, depending on their dependencies/requirements (to
    other stacks, and usually it is done automatically though manual
    dependencies can be specified in the config).

    If a stack already exists, but it's template or parameters have changed
    it updates the stack, handling dependencies.

    Also manages the translation of Output's to Parameters between stacks,
    allowing you to pull information from one stack and use it in another.
    """

    def __init__(self, region, namespace, mappings=None, parameters=None):
        self.region = region
        self.mappings = mappings or {}
        self.parameters = parameters or {}
        self.namespace = namespace
        self.cfn_base = namespace.replace('.', '-').lower()
        self.bucket_name = "stacker-%s" % self.cfn_base

        self._conn = None
        self._cfn_bucket = None

        self.reset()

    @property
    def conn(self):
        if not getattr(self, '_conn', None):
            self._conn = ConnectionManager(self.region)
        return self._conn

    @property
    def s3_conn(self):
        if not hasattr(self, '_s3_conn'):
            self._s3_conn = ConnectionManager().s3
        return self._s3_conn

    @property
    def cfn_bucket(self):
        if not getattr(self, '_cfn_bucket', None):
            try:
                self._cfn_bucket = self.s3_conn.get_bucket(self.bucket_name)
            except S3ResponseError, e:
                if e.error_code == 'NoSuchBucket':
                    logger.debug("Creating bucket %s.", self.bucket_name)
                    self._cfn_bucket = self.s3_conn.create_bucket(
                        self.bucket_name,
                        location=get_bucket_location(self.region))
                elif e.error_code == 'AccessDenied':
                    logger.exception("Access denied for bucket %s.",
                                     self.bucket_name)
                    raise
                else:
                    logger.exception("Error creating bucket %s.",
                                     self.bucket_name)
                    raise
        return self._cfn_bucket

    def reset(self):
        self.plan = Plan()
        self.outputs = {}

    def get_stack_full_name(self, stack_name):
        return get_stack_full_name(self.cfn_base, stack_name)

    def stack_template_url(self, blueprint):
        return stack_template_url(self.bucket_name, blueprint)

    def s3_stack_push(self, blueprint, force=False):
        """ Pushes the rendered blueprint's template to S3.

        Verifies that the template doesn't already exist in S3 before
        pushing.

        Returns the URL to the template in S3.
        """
        key_name = stack_template_key_name(blueprint)
        template_url = self.stack_template_url(blueprint)
        if self.cfn_bucket.get_key(key_name) and not force:
            logger.debug("Cloudformation template %s already exists.",
                         template_url)
            return template_url
        key = self.cfn_bucket.new_key(key_name)
        key.set_contents_from_string(blueprint.rendered)
        logger.debug("Blueprint %s pushed to %s.", blueprint.name,
                     template_url)
        return template_url

    def get_stack_status(self, stack_name):
        """ Get the status of a CloudFormation stack. """
        stack_info = self.conn.cloudformation.describe_stacks(stack_name)
        return stack_info[0].stack_status

    def get_pending_stacks(self, stack_set):
        """ For stack in stack_set, return a set of stacks that are still
        not complete (either not submitted or just not complete).
        """
        pending = self.plan.list_pending()
        result = {}
        for stack in stack_set:
            if stack in pending:
                result[stack] = self.plan[stack].status
        return result

    def build_blueprint(self, stack_context):
        """ Build a Blueprint object for the given stack context.

        Applys the blueprint to the stack_context in the plan.
        """
        stack_name = stack_context.name
        try:
            blueprint = self.plan[stack_name].blueprint
            if blueprint:
                return blueprint
        except (KeyError, AttributeError):
            pass
        cls = load_object_from_string(stack_context.class_path)
        if not hasattr(cls, 'rendered'):
            raise AttributeError("Stack class %s does not have a "
                                 "'rendered' "
                                 "attribute." % (stack_context.class_path))
        blueprint = cls(name=stack_name, context=stack_context,
                        mappings=self.mappings)
        self.plan[stack_name].blueprint = blueprint
        return blueprint

    def resolve_parameters(self, parameters, blueprint):
        """ Resolves parameters for a given blueprint.

        Given a list of parameters, first discard any parameters that the
        blueprint does not use. Then, if a remaining parameter is in the format
        <stack_name>::<output_name>, pull that output from the foreign
        stack.

        Args:
            parameters (dict): A dictionary of parameters provided by the
                               stack definition
            blueprint (Blueprint): A stacker.blueprint.base.Blueprint object
                                   that is having the parameters applied to
                                   it.

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
                # Get from the Output of another stack in the stack_map
                stack_name, output = value.split('::')
                stack_outputs = self.get_outputs(stack_name)
                try:
                    value = stack_outputs[output]
                except KeyError:
                    raise ParameterDoesNotExist(value)
            params[k] = value
        return params

    def get_stack(self, stack_full_name):
        """ Give a stacks full name, query for the boto Stack object.

        If no stack exists with that name, return None.
        """
        try:
            return self.conn.cloudformation.describe_stacks(stack_full_name)[0]
        except BotoServerError as e:
            if 'does not exist' not in e.message:
                raise
        return None

    def build_stack_tags(self, stack_context, template_url):
        """ Builds a common set of tags to attach to a stack.
        """
        requires = [
            self.get_stack_full_name(s) for s in stack_context.requires]
        logger.debug("Stack %s required stacks: %s",
                     stack_context.name, requires)
        tags = {'template_url': template_url,
                'stacker_namespace': self.namespace}
        if requires:
            tags['required_stacks'] = ':'.join(requires)
        return tags

    def create_stack(self, full_name, template_url, parameters, tags):
        """ Creates a stack in CloudFormation """
        logger.info("Stack %s not found, creating.", full_name)
        logger.debug("Using parameters: %s", parameters)
        logger.debug("Using tags: %s", tags)
        self.conn.cloudformation.create_stack(full_name,
                                              template_url=template_url,
                                              parameters=parameters, tags=tags,
                                              capabilities=['CAPABILITY_IAM'])
        return SUBMITTED

    def update_stack(self, full_name, template_url, parameters, tags):
        """ Updates an existing stack in CloudFormation. """
        try:
            logger.info("Attempting to update stack %s.", full_name)
            self.conn.cloudformation.update_stack(
                full_name, template_url=template_url, parameters=parameters,
                tags=tags, capabilities=['CAPABILITY_IAM'])
            return SUBMITTED
        except BotoServerError as e:
            if 'No updates are to be performed.' in e.message:
                logger.info("Stack %s did not change, not updating.",
                            full_name)
                return SKIPPED
            raise

    def launch_stack(self, stack_name, blueprint):
        """ Handles the creating or updating of a stack in CloudFormation.

        Also makes sure that we don't try to create or update a stack while
        it is already updating or creating.
        """
        full_name = self.get_stack_full_name(stack_name)
        stack_context = self.plan[stack_name]
        stack = self.get_stack(full_name)
        if stack and stack.stack_status in INPROGRESS_STATUSES:
            logger.debug("Stack %s in progress with %s status.",
                         full_name, stack.stack_status)
            return
        logger.info("Launching stack %s now.", stack_name)
        template_url = self.s3_stack_push(blueprint)
        tags = self.build_stack_tags(stack_context, template_url)
        parameters = self.resolve_parameters(stack_context.parameters,
                                             blueprint)
        required_params = [k for k, v in blueprint.required_parameters]
        parameters = handle_missing_parameters(parameters, required_params,
                                               stack)
        status = PENDING
        if not stack:
            status = self.create_stack(full_name, template_url, parameters,
                                       tags)
        else:
            status = self.update_stack(full_name, template_url, parameters,
                                       tags)

        stack_context.set_status(status)

    def get_outputs(self, stack_name, force=False):
        """ Gets all the outputs from a given stack in CloudFormation.

        Updates the local output cache with the values it finds.
        """
        if stack_name in self.outputs and not force:
            return self.outputs[stack_name]

        logger.debug("Getting outputs from stack %s.", stack_name)

        full_name = self.get_stack_full_name(stack_name)
        stack = self.get_stack(full_name)
        if not stack:
            logger.debug("Stack %s does not exist, skipping.", full_name)
            return
        stack_outputs = {}
        self.outputs[stack_name] = stack_outputs
        for output in stack.outputs:
            logger.debug("    %s: %s", output.key, output.value)
            stack_outputs[output.key] = output.value
        return self.outputs[stack_name]

    def sync_plan_status(self):
        """ Updates the status of each stack in the local plan.

        For each stack listed as 'pending' but 'submitted' in the local plan,
        query CloudFormation for the stack's status.

        If the status is one of the COMPLETE_STATUSES, then mark it as
        complete in the local plan.
        """
        for stack_name in self.plan.list_pending():
            stack_context = self.plan[stack_name]
            full_name = self.get_stack_full_name(stack_name)
            local_status = stack_context.status
            # We only update local status on stacks that have been marked
            # locally as submitted
            if not local_status == SUBMITTED:
                logger.debug("Stack %s not submitted yet.", stack_name)
                continue
            cf_status = self.get_stack_status(full_name)
            logger.debug("Stack %s cloudformation status: %s", full_name,
                         cf_status)
            if cf_status in COMPLETE_STATUSES:
                logger.info("Stack %s complete: %s", stack_name, cf_status)
                stack_context.complete()

    def build_plan(self, stack_definitions):
        """ Creates the plan for building out the defined stacks. """
        plan = Plan()
        for stack_def in stack_definitions:
            # Combine the Builder parameters with the stack parameters
            stack_def['namespace'] = self.namespace
            stack_def['parameters'] = gather_parameters(stack_def,
                                                        self.parameters)
            plan.add(stack_def)
        return plan

    def build(self, stack_definitions):
        """ Kicks off the build/update of the stacks in the stack_definitions.

        This is the main entry point for the Builder.
        """
        self.reset()
        self.plan = self.build_plan(stack_definitions)
        logger.info("Launching stacks: %s", ', '.join(self.plan.keys()))

        attempts = 0
        while not self.plan.completed:
            attempts += 1
            self.sync_plan_status()
            pending_stacks = self.plan.list_pending()
            submitted_stacks = self.plan.list_submitted()
            if not attempts % 10:
                logger.info("Waiting on stacks: %s",
                            ', '.join(submitted_stacks))
            for stack_name in pending_stacks:
                stack_context = self.plan[stack_name]
                requires = stack_context.requires
                pending_required = self.get_pending_stacks(requires)
                if pending_required:
                    logger.debug("Stack %s waiting on required stacks: "
                                 "%s", stack_name, ', '.join(pending_required))
                    continue
                blueprint = self.build_blueprint(stack_context)
                self.launch_stack(stack_name, blueprint)
            time.sleep(5)
