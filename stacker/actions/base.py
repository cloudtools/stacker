import logging

import boto

logger = logging.getLogger(__name__)


def stack_template_key_name(blueprint):
    return "%s-%s.json" % (blueprint.name, blueprint.version)


def stack_template_url(bucket_name, blueprint):
    key_name = stack_template_key_name(blueprint)
    return "https://s3.amazonaws.com/%s/%s" % (bucket_name, key_name)


class BaseAction(object):

    def __init__(self, context, provider=None):
        self.context = context
        self.provider = provider
        self.bucket_name = 'stacker-%s' % (context.get_fqn(),)
        self._conn = None
        self._cfn_bucket = None

    @property
    def s3_conn(self):
        if not hasattr(self, '_s3_conn'):
            self._s3_conn = boto.connect_s3()
        return self._s3_conn

    @property
    def cfn_bucket(self):
        if not getattr(self, '_cfn_bucket', None):
            try:
                self._cfn_bucket = self.s3_conn.get_bucket(self.bucket_name)
            except boto.exception.S3ResponseError, e:
                if e.error_code == 'NoSuchBucket':
                    logger.debug("Creating bucket %s.", self.bucket_name)
                    self._cfn_bucket = self.s3_conn.create_bucket(self.bucket_name)
                elif e.error_code == 'AccessDenied':
                    logger.exception("Access denied for bucket %s.",
                                     self.bucket_name)
                    raise
                else:
                    logger.exception("Error creating bucket %s.",
                                     self.bucket_name)
                    raise
        return self._cfn_bucket

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

    def run(self, *args, **kwargs):
        raise NotImplementedError('Subclass must implement "run" method')

    def _get_all_stack_names(self, dependency_dict):
        return set(
            dependency_dict.keys() +
            [item for dependencies in dependency_dict.values() for item in dependencies]
        )

    def get_stack_execution_order(self, dependency_dict):
        pending_steps = []
        executed_steps = []
        stack_names = self._get_all_stack_names(dependency_dict)
        for stack_name in stack_names:
            requirements = dependency_dict.get(stack_name, None)
            if not requirements:
                dependency_dict.pop(stack_name, None)
                pending_steps.append(stack_name)

        while dependency_dict:
            for step in pending_steps:
                for stack_name, requirements in dependency_dict.items():
                    if step in requirements:
                        requirements.remove(step)

                    if not requirements:
                        dependency_dict.pop(stack_name)
                        pending_steps.append(stack_name)
                pending_steps.remove(step)
                executed_steps.append(step)
        return executed_steps + pending_steps
