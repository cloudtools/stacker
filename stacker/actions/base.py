import copy
import logging

import boto

logger = logging.getLogger(__name__)


def stack_template_key_name(blueprint):
    """Given a blueprint, produce an appropriate key name.

    Args:
        blueprint (:class:`stacker.blueprints.base.Blueprint`): The blueprint
            object to create the key from.

    Returns:
        string: Key name resulting from blueprint.
    """
    return "%s-%s.json" % (blueprint.name, blueprint.version)


def stack_template_url(bucket_name, blueprint):
    """Produces an s3 url for a given blueprint.

    Args:
        bucket_name (string): The name of the S3 bucket where the resulting
            templates are stored.
        blueprint (:class:`stacker.blueprints.base.Blueprint`): The blueprint
            object to create the URL to.

    Returns:
        string: S3 URL.
    """
    key_name = stack_template_key_name(blueprint)
    return "https://s3.amazonaws.com/%s/%s" % (bucket_name, key_name)


class BaseAction(object):
    """Actions perform the actual work of each Command.

    Each action is tied to a :class:`stacker.commands.base.BaseCommand`, and
    is responsible for building the :class:`stacker.plan.Plan` that will be
    executed to perform that command.

    Args:
        context (:class:`stacker.context.Context`): The stacker context for
            the current run.
        provider (Optional(:class:`stacker.providers.base.BaseProvider`)):
            The provider that will be interacted with in order to perform
            the necessary actions.
    """

    def __init__(self, context, provider=None):
        self.context = context
        self.provider = provider
        self.bucket_name = context.bucket_name
        self._conn = None
        self._cfn_bucket = None

    @property
    def s3_conn(self):
        """The boto s3 connection object used for communication with S3."""
        if not hasattr(self, '_s3_conn'):
            self._s3_conn = boto.connect_s3()
        return self._s3_conn

    @property
    def cfn_bucket(self):
        """The cloudformation bucket where templates will be stored."""
        if not getattr(self, '_cfn_bucket', None):
            try:
                self._cfn_bucket = self.s3_conn.get_bucket(self.bucket_name)
            except boto.exception.S3ResponseError, e:
                if e.error_code == 'NoSuchBucket':
                    logger.debug("Creating bucket %s.", self.bucket_name)
                    self._cfn_bucket = self.s3_conn.create_bucket(
                        self.bucket_name)
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
        """Pushes the rendered blueprint's template to S3.

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

    def execute(self, *args, **kwargs):
        self.pre_run(*args, **kwargs)
        self.run(*args, **kwargs)
        self.post_run(*args, **kwargs)

    def pre_run(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        raise NotImplementedError('Subclass must implement "run" method')

    def post_run(self, *args, **kwargs):
        pass

    def _get_all_stack_names(self, dependencies):
        """Get all stack names specified in dependencies.

        Args:
            - dependencies (dict): a dictionary where each key should be the
                fully qualified name of a stack whose value is an array of
                fully qualified stack names that the stack depends on.

        Returns:
            set: set of all stack names

        """
        return set(
            dependencies.keys() +
            [item for items in dependencies.values() for item in items]
        )

    def get_stack_execution_order(self, dependencies):
        """Return the order in which the stacks should be executed.

        Args:
            - dependencies (dict): a dictionary where each key should be the
                fully qualified name of a stack whose value is an array of
                fully qualified stack names that the stack depends on. This is
                used to generate the order in which the stacks should be
                executed.

        Returns:
            array: An array of stack names in the order which they should be
                executed.

        """
        # copy the dependencies since we pop items out of it to get the
        # execution order, we don't want to mutate the one passed in
        dependencies = copy.deepcopy(dependencies)
        pending_steps = []
        executed_steps = []
        stack_names = self._get_all_stack_names(dependencies)
        for stack_name in stack_names:
            requirements = dependencies.get(stack_name, None)
            if not requirements:
                dependencies.pop(stack_name, None)
                pending_steps.append(stack_name)

        while dependencies:
            for step in pending_steps:
                for stack_name, requirements in dependencies.items():
                    if step in requirements:
                        requirements.remove(step)

                    if not requirements:
                        dependencies.pop(stack_name)
                        pending_steps.append(stack_name)
                pending_steps.remove(step)
                executed_steps.append(step)
        return executed_steps + pending_steps
