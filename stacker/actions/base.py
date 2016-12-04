import logging

import boto3
import botocore.exceptions

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
        provider (:class:`stacker.providers.base.BaseProvider`, optional):
            The provider that will be interacted with in order to perform
            the necessary actions.
    """

    def __init__(self, context, provider=None):
        self.context = context
        self.provider = provider
        self.bucket_name = context.bucket_name
        self._conn = None

    @property
    def s3_conn(self):
        """The boto s3 connection object used for communication with S3."""
        if not hasattr(self, "_s3_conn"):
            session = boto3.Session(region_name=self.provider.region)
            self._s3_conn = session.client('s3')
        return self._s3_conn

    def ensure_cfn_bucket(self):
        """The cloudformation bucket where templates will be stored."""
        try:
            self.s3_conn.head_bucket(Bucket=self.bucket_name)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Message'] == "Not Found":
                logger.debug("Creating bucket %s.", self.bucket_name)
                self.s3_conn.create_bucket(Bucket=self.bucket_name)
            elif e.response['Error']['Message'] == "Forbidden":
                logger.exception("Access denied for bucket %s.",
                                 self.bucket_name)
                raise
            else:
                logger.exception("Error creating bucket %s. Error %s",
                                 self.bucket_name, e.response)
                raise

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
        self.ensure_cfn_bucket()
        try:
            template_exists = self.s3_conn.head_object(
                Bucket=self.bucket_name, Key=key_name) is not None
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                template_exists = False
            else:
                raise

        if template_exists and not force:
            logger.debug("Cloudformation template %s already exists.",
                         template_url)
            return template_url
        self.s3_conn.put_object(Bucket=self.bucket_name,
                                Key=key_name,
                                Body=blueprint.rendered,
                                ServerSideEncryption='AES256')
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
        raise NotImplementedError("Subclass must implement \"run\" method")

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
