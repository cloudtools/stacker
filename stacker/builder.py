import logging
import copy
from collections import OrderedDict, Iterable
import time

logger = logging.getLogger(__name__)

from aws_helper.connection import ConnectionManager

from boto.exception import S3ResponseError, BotoServerError

from .util import (create_route53_zone, load_object_from_string,
                   find_subnetable_zones)


INPROGRESS_STATUSES = ('CREATE_IN_PROGRESS',
                       'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                       'UPDATE_IN_PROGRESS')
COMPLETE_STATUSES = ('CREATE_COMPLETE', 'UPDATE_COMPLETE')

STATUS_SUBMITTED = 1
STATUS_COMPLETE = 2


class StackConfig(object):
    def __init__(self, name, class_path, requires=None, parameters=None):
        self.name = name
        self.class_path = class_path
        self.parameters = parameters or {}
        requires = requires or []
        self._requires = set(requires)

        self.template = None
        self.status = None

    def __repr__(self):
        return self.name

    @property
    def completed(self):
        return self.status == STATUS_COMPLETE

    @property
    def submitted(self):
        return self.status >= STATUS_SUBMITTED

    @property
    def requires(self):
        requires = copy.deepcopy(self._requires)
        # Auto add dependencies when parameters reference the Ouptuts of
        # another stack.
        parameters = self.parameters
        for value in parameters.values():
            if isinstance(value, basestring) and '::' in value:
                stack_name, _ = value.split('::')
            else:
                continue
            if stack_name not in requires:
                requires.add(stack_name)
        return requires

    def complete(self):
        logger.debug("Setting %s state to complete.", self.name)
        self.status = STATUS_COMPLETE

    def submit(self):
        logger.debug("Setting %s state to submitted.", self.name)
        self.status = STATUS_SUBMITTED


class TaskTracker(OrderedDict):
    def add(self, definition):
        self[definition['name']] = StackConfig(**definition)

    def _parse_items(self, items):
        if isinstance(items, Iterable) and not isinstance(items, basestring):
            return items
        return [items, ]

    def complete(self, items):
        items = self._parse_items(items)
        for i in items:
            self[i].complete()

    def submit(self, items):
        items = self._parse_items(items)
        for i in items:
            self[i].submit()

    def list_completed(self):
        result = OrderedDict()
        for k, record in self.items():
            if record.status == STATUS_COMPLETE:
                result[k] = record
        return result

    def list_pending(self):
        result = OrderedDict()
        for k, record in self.items():
            if record.status != STATUS_COMPLETE:
                result[k] = record
        return result

    def list_submitted(self):
        result = OrderedDict()
        for k, record in self.items():
            if record.status == STATUS_SUBMITTED:
                result[k] = record
        return result

    @property
    def completed(self):
        if self.list_pending():
            return False
        return True


class StackBuilder(object):
    def __init__(self, region, mappings=None, config=None,
                 parameters=None, max_zone_count=None):
        self.region = region
        self.domain = parameters["BaseDomain"]
        self.mappings = mappings or {}
        self.config = config or {}
        self.parameters = parameters or {}
        self._conn = None
        self.max_zone_count = max_zone_count
        self._cfn_bucket = None
        self.cfn_domain = self.domain.replace('.', '-')

        self.reset()

    @property
    def conn(self):
        if not getattr(self, '_conn', None):
            self._conn = ConnectionManager(self.region)
        return self._conn

    @property
    def cfn_bucket(self):
        if not getattr(self, '_cfn_bucket', None):
            s3 = self.conn.s3
            try:
                self._cfn_bucket = s3.get_bucket(self.cfn_domain)
            except S3ResponseError, e:
                if e.error_code == 'NoSuchBucket':
                    logger.debug("Creating bucket %s.", self.cfn_domain)
                    self._cfn_bucket = s3.create_bucket(self.cfn_domain)
                else:
                    logger.exception("Error creating bucket %s.",
                                     self.cfn_domain)
                    raise
        return self._cfn_bucket

    def verify_zone_availability(self):
        return find_subnetable_zones(self.conn.vpc)

    def reset(self):
        self.stacks = TaskTracker()
        self.outputs = {}

    def get_stack_full_name(self, stack_name):
        return "%s-%s" % (self.cfn_domain, stack_name)

    def stack_template_key_name(self, stack_template):
        return "%s-%s.json" % (stack_template.name, stack_template.version)

    def stack_template_url(self, stack_template):
        key_name = self.stack_template_key_name(stack_template)
        return "https://s3.amazonaws.com/%s/%s" % (self.cfn_domain,
                                                   key_name)

    def s3_stack_push(self, stack_template, force=False):
        key_name = self.stack_template_key_name(stack_template)
        template_url = self.stack_template_url(stack_template)
        if self.cfn_bucket.get_key(key_name) and not force:
            logger.debug("Cloudformation template %s already exists.",
                         template_url)
            return template_url
        key = self.cfn_bucket.new_key(key_name)
        key.set_contents_from_string(stack_template.rendered)
        return template_url

    def setup_prereqs(self):
        create_route53_zone(self.conn.route53, self.domain)

    def get_cf_stack_status(self, stack_name):
        stack_info = self.conn.cloudformation.describe_stacks(stack_name)
        return stack_info[0].stack_status

    def get_pending_stacks(self, stack_set):
        """ For stack in stack_set, return a set of stacks that are still
        not complete (either not submitted or just not complete).
        """
        pending = self.stacks.list_pending()
        result = {}
        for stack in stack_set:
            if stack in pending:
                result[stack] = self.stacks[stack].status
        return result

    def build_template(self, stack_config):
        stack_name = stack_config.name
        try:
            template = self.stacks[stack_name].template
            if template:
                return template
        except (KeyError, AttributeError):
            pass
        class_path = stack_config.class_path
        cls = load_object_from_string(class_path)
        if not hasattr(cls, 'rendered'):
            raise AttributeError("Stack class %s does not have a "
                                 "'rendered' "
                                 "attribute." % (class_path))
        template = cls(self.region, name=stack_name, mappings=self.mappings,
                       config=stack_config)
        self.stacks[stack_name].template = template
        return template

    def resolve_parameters(self, parameters, stack):
        params = []
        for k, v in parameters.items():
            if k not in stack.template.parameters:
                logger.debug("Template %s does not use parameter %s.",
                             stack.name, k)
                continue
            value = v
            if isinstance(value, basestring) and '::' in value:
                # Get from the Output of another stack in the stack_map
                stack_name, output = value.split('::')
                self.get_outputs(stack_name)
                value = self.outputs[stack_name][output]
            params.append((k, value))
        return params

    def launch_stack(self, stack_name, template):
        cf = self.conn.cloudformation
        full_name = self.get_stack_full_name(stack_name)
        stack_config = self.stacks[stack_name]
        stack = None
        try:
            stack = cf.describe_stacks(full_name)[0]
        except BotoServerError as e:
            if 'does not exist' not in e.message:
                raise
        if stack and stack.stack_status in INPROGRESS_STATUSES:
            logger.debug("Stack %s in progress with %s status.",
                         full_name, stack.stack_status)
            return
        template_url = self.s3_stack_push(template)
        params = stack_config.parameters
        parameters = self.resolve_parameters(params, template)
        requires = [self.get_stack_full_name(s) for s in stack_config.requires]
        logger.debug("Stack %s required stacks: %s", stack_name, requires)
        tags = {'template_url': template_url}
        if requires:
            tags['required_stacks'] = ':'.join(requires)
        if not stack:
            logger.info("Stack %s not found, creating.", full_name)
            logger.debug("Using parameters: %s", parameters)
            logger.debug("Using tags: %s", tags)
            cf.create_stack(full_name, template_url=template_url,
                            parameters=parameters,
                            tags=tags,
                            capabilities=['CAPABILITY_IAM'])
            stack_config.submit()
        else:
            try:
                logger.info("Attempting to update stack %s.", full_name)
                cf.update_stack(full_name, template_url=template_url,
                                parameters=parameters,
                                tags=tags,
                                capabilities=['CAPABILITY_IAM'])
                stack_config.submit()
            except BotoServerError as e:
                if 'No updates are to be performed.' in e.message:
                    logger.info("Stack %s did not change, not updating.",
                                stack_name)
                    stack_config.submit()
                    return
                raise

    def get_outputs(self, stack_name, force=False):
        logger.debug("Getting outputs from stack %s.", stack_name)
        if stack_name in self.outputs and not force:
            return

        full_name = self.get_stack_full_name(stack_name)
        cf = self.conn.cloudformation
        stack = cf.describe_stacks(full_name)[0]
        stack_outputs = {}
        self.outputs[stack_name] = stack_outputs
        for output in stack.outputs:
            logger.debug("    %s: %s", output.key, output.value)
            stack_outputs[output.key] = output.value

    def update_stack_status(self):
        for stack_name in self.stacks.list_pending():
            stack_record = self.stacks[stack_name]
            full_name = self.get_stack_full_name(stack_name)
            local_status = stack_record.status
            # We only update local status on stacks that have been marked
            # locally as submitted
            if not local_status == STATUS_SUBMITTED:
                logger.debug("Stack %s not submitted yet.", stack_name)
                continue
            logger.debug("Getting '%s' stack state from AWS.", stack_name)
            cf_status = self.get_cf_stack_status(full_name)
            logger.debug("Stack %s cloudformation status: %s", stack_name,
                         cf_status)
            if cf_status in COMPLETE_STATUSES:
                logger.info("Stack %s complete: %s", stack_name, cf_status)
                stack_record.complete()

    def build(self, stack_definitions):
        self.reset()
        self.parameters['Zones'] = \
            self.verify_zone_availability()[:self.max_zone_count]
        self.setup_prereqs()
        for stack_def in stack_definitions:
            # Combine the Builder parameters with the stack parameters
            stack_def['parameters'].update(self.parameters)
            self.stacks.add(stack_def)
        logger.info("Launching stacks: %s", ', '.join(self.stacks.keys()))

        attempts = 0
        while not self.stacks.completed:
            attempts += 1
            self.update_stack_status()
            pending_stacks = self.stacks.list_pending()
            submitted_stacks = self.stacks.list_submitted()
            if not attempts % 10:
                logger.info("Waiting on stacks: %s",
                            ', '.join(submitted_stacks))
            for stack_name in pending_stacks:
                stack_config = self.stacks[stack_name]
                requires = stack_config.requires
                pending_required = self.get_pending_stacks(requires)
                if pending_required:
                    logger.debug("Stack %s still waiting on required stacks: "
                                 "%s", stack_name, ', '.join(pending_required))
                    continue
                logger.debug("All required stacks are finished, building %s "
                             "now.", stack_name)
                template = self.build_template(stack_config)
                self.launch_stack(stack_name, template)
            time.sleep(5)
