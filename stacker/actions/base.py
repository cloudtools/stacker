import threading
import logging

from colorama.ansi import Fore

from ..plan import Step
from ..status import (
    SUBMITTED,
    COMPLETE,
)

import botocore.exceptions
from stacker.session_cache import get_session

logger = logging.getLogger(__name__)


def outline_plan(plan, level=logging.INFO, message=""):
    """Print an outline of the actions the plan is going to take.
    The outline will represent the rough ordering of the steps that will be
    taken.
    Args:
        level (int, optional): a valid log level that should be used to log
            the outline
        message (str, optional): a message that will be logged to
            the user after the outline has been logged.
    """
    steps = 1
    logger.log(level, "Plan \"%s\":", plan.description)

    nodes = plan.dag.topological_sort()
    nodes.reverse()
    for step_name in nodes:
        step = plan.steps[step_name]
        logger.log(
            level,
            "  - step: %s: target: \"%s\", action: \"%s\"",
            steps,
            step_name,
            step.fn.__name__,
        )
        steps += 1

    if message:
        logger.log(level, message)


def check_point_fn():
    """Adds a check_point function to each of the given steps."""

    lock = threading.Lock()

    def _fn(plan):
        lock.acquire()
        _check_point(plan)
        lock.release()

    return _fn


def _check_point(plan):
    """Outputs the current status of all steps in the plan."""
    status_to_color = {
        SUBMITTED.code: Fore.YELLOW,
        COMPLETE.code: Fore.GREEN,
    }
    logger.info("Plan Status:", extra={"reset": True, "loop": plan.id})

    longest = 0
    messages = []

    nodes = plan.dag.topological_sort()
    nodes.reverse()
    for step_name in nodes:
        step = plan.steps[step_name]

        length = len(step.name)
        if length > longest:
            longest = length

        msg = "%s: %s" % (step.name, step.status.name)
        if step.status.reason:
            msg += " (%s)" % (step.status.reason)

        messages.append((msg, step))

    for msg, step in messages:
        parts = msg.split(' ', 1)
        fmt = "\t{0: <%d}{1}" % (longest + 2,)
        color = status_to_color.get(step.status.code, Fore.WHITE)
        logger.info(fmt.format(*parts), extra={
            'loop': plan.id,
            'color': color,
            'last_updated': step.last_updated,
        })


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

    def __init__(self, context, provider=None, cancel=None):
        self.context = context
        self.provider = provider
        self.bucket_name = context.bucket_name
        self._conn = None
        self.cancel = cancel or threading.Event()

    def _action(self):
        raise NotImplementedError

    @property
    def steps(self):
        if not hasattr(self, "_steps"):
            self._steps = [
                Step(stack, fn=self._action)
                for stack in self.context.get_stacks()]
        return self._steps

    @property
    def s3_conn(self):
        """The boto s3 connection object used for communication with S3."""
        if not hasattr(self, "_s3_conn"):
            session = get_session(self.provider.region)
            self._s3_conn = session.client('s3')

        return self._s3_conn

    def ensure_cfn_bucket(self):
        """The CloudFormation bucket where templates will be stored."""
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
