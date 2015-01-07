import logging
import copy
import re

logger = logging.getLogger(__name__)

from aws_helper.connection import ConnectionManager
from troposphere.cloudformation import Stack
from troposphere import GetAtt

from boto.exception import S3ResponseError

from .stack import StackTemplateBase
from .util import (create_route53_zone, load_object_from_string, cf_safe_name,
                   find_subnetable_zones)


class MasterStack(StackTemplateBase):
    def __init__(self, region, name=None, mappings=None, config=None):
        super(MasterStack, self).__init__(region, name, mappings, config)
        self.sub_stacks = []

    def add_sub_stack(self, stack):
        self.sub_stacks.append(stack)

    def create_template(self):
        for s in self.sub_stacks:
            self.template.add_resource(s)


class StackBuilder(object):
    def __init__(self, region, domain, mappings=None, config=None):
        self.region = region
        self.domain = domain
        self.mappings = mappings or {}
        self.config = config or {}
        self._conn = None
        if 'zones' not in self.config:
            self.config['zones'] = self.verify_zone_availability()
        max_zone_count = self.config.get('max_zone_count',
                                         len(self.config['zones']))
        self.config['zones'] = self.config['zones'][:max_zone_count]

        self._cfn_bucket = None

        self.cfn_domain = domain.replace('.', '-')

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
        self.master_stack = MasterStack(self.region, name='master',
                                        mappings=self.mappings,
                                        config=self.config)

    def stack_template_key_name(self, stack):
        return "%s-%s.json" % (stack.name, stack.version)

    def stack_template_url(self, stack):
        key_name = self.stack_template_key_name(stack)
        return "https://s3.amazonaws.com/%s/%s" % (self.cfn_domain,
                                                   key_name)

    def s3_stack_push(self, stack, force=False):
        key_name = self.stack_template_key_name(stack)
        template_url = self.stack_template_url(stack)
        if self.cfn_bucket.get_key(key_name) and not force:
            logger.info("Cloudformation template %s already exists.",
                        template_url)
            return template_url
        key = self.cfn_bucket.new_key(key_name)
        key.set_contents_from_string(stack.rendered)
        return template_url

    def resolve_parameters(self, parameters, stack_map, template):
        params = {}
        for k, v in parameters.items():
            if k not in template.template.parameters:
                logger.info("Template %s does not use parameter %s.",
                            template, k)
                continue
            value = v
            if isinstance(value, basestring) and '::' in value:
                # Get from the Output of another stack in the stack_map
                stack_name, output = value.split('::')
                output = "Outputs.%s" % output
                value = GetAtt(stack_map[stack_name], output)
            params[k] = value
        return params

    def resolve_depends(self, stack_config, stack_map):
        depends = {}
        for d in stack_config.get('depends', []):
            depends[d] = cf_safe_name(d)
        # Auto add dependencies when parameters reference the Ouptuts of
        # another stack.
        parameters = stack_config.get('parameters', {})
        for value in parameters.values():
            if isinstance(value, basestring) and '::' in value:
                stack_name, output = value.split('::')
            else:
                continue
            if stack_name not in depends:
                depends[stack_name] = cf_safe_name(stack_name)
        # Check that the dependency stack is already created.
        for d in depends:
            if d not in stack_map:
                raise Exception("Dependency %s not found in stack "
                                "definitions." % d)
        return depends.values()

    def build(self, stack_definitions):
        self.reset()
        cf = self.conn.cloudformation
        create_route53_zone(self.conn.route53, self.domain)
        # stack_name: template
        stack_map = {}
        for stack_def in stack_definitions:
            stack_name = stack_def.get('name', None)
            conf = copy.deepcopy(self.config)
            conf.update(stack_def.get('config', {}))
            cls = load_object_from_string(stack_def['class'])
            if not hasattr(cls, 'rendered'):
                raise AttributeError("Stack class %s does not have a "
                                     "'rendered' "
                                     "attribute." % (stack_def['class']))
            template = cls(self.region, name=stack_name,
                           mappings=self.mappings, config=conf)
            safe_stack_name = cf_safe_name(template.name)
            template_url = self.s3_stack_push(template)
            parameters = self.resolve_parameters(
                stack_def.get('parameters', {}), stack_map, template)
            depends = self.resolve_depends(stack_def, stack_map)
            stack_obj = Stack(safe_stack_name, TemplateURL=template_url,
                              Parameters=parameters, DependsOn=depends)
            stack_map[stack_name] = stack_obj
            self.master_stack.add_sub_stack(stack_obj)
        master_url = self.s3_stack_push(self.master_stack)
        return master_url

    def create_stack(self, stack_definitions):
        master_url = self.build(stack_definitions)
        cf = self.conn.cloudformation
        cf.create_stack(self.cfn_domain, template_url=master_url,
                        tags={'template_url': master_url},
                        capabilities=['CAPABILITY_IAM'])

    def update_stack(self, stack_definitions):
        master_url = self.build(stack_definitions)
        cf = self.conn.cloudformation
        cf.update_stack(self.cfn_domain, template_url=master_url,
                        tags={'template_url': master_url},
                        capabilities=['CAPABILITY_IAM'])
