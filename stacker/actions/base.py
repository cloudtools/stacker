from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import os
import sys
import logging
import threading

from ..dag import walk, ThreadedWalker
from ..plan import Step, build_plan

import botocore.exceptions
from stacker.session_cache import get_session
from stacker.exceptions import PlanFailed

from stacker.util import (
    ensure_s3_bucket,
    get_s3_endpoint,
)

logger = logging.getLogger(__name__)

# After submitting a stack update/create, this controls how long we'll wait
# between calls to DescribeStacks to check on it's status. Most stack updates
# take at least a couple minutes, so 30 seconds is pretty reasonable and inline
# with the suggested value in
# https://github.com/boto/botocore/blob/1.6.1/botocore/data/cloudformation/2010-05-15/waiters-2.json#L22
#
# This can be controlled via an environment variable, mostly for testing.
STACK_POLL_TIME = int(os.environ.get("STACKER_STACK_POLL_TIME", 30))


def build_walker(concurrency):
    """This will return a function suitable for passing to
    :class:`stacker.plan.Plan` for walking the graph.

    If concurrency is 1 (no parallelism) this will return a simple topological
    walker that doesn't use any multithreading.

    If concurrency is 0, this will return a walker that will walk the graph as
    fast as the graph topology allows.

    If concurrency is greater than 1, it will return a walker that will only
    execute a maximum of concurrency steps at any given time.

    Returns:
        func: returns a function to walk a :class:`stacker.dag.DAG`.
    """
    if concurrency == 1:
        return walk
    return ThreadedWalker(concurrency).walk


def plan(description, action, stacks,
         targets=None, tail=None,
         reverse=False):
    """A simple helper that builds a graph based plan from a set of stacks.

    Args:
        description (str): a description of the plan.
        action (func): a function to call for each stack.
        stacks (list): a list of :class:`stacker.stack.Stack` objects to build.
        targets (list): an optional list of targets to filter the graph to.
        tail (func): an optional function to call to tail the stack progress.
        reverse (bool): if True, execute the graph in reverse (useful for
            destroy actions).

    Returns:
        :class:`plan.Plan`: The resulting plan object
    """

    steps = [
        Step(stack, fn=action, watch_func=tail)
        for stack in stacks]

    return build_plan(
        description=description,
        steps=steps,
        targets=targets,
        reverse=reverse)


def stack_template_key_name(blueprint):
    """Given a blueprint, produce an appropriate key name.

    Args:
        blueprint (:class:`stacker.blueprints.base.Blueprint`): The blueprint
            object to create the key from.

    Returns:
        string: Key name resulting from blueprint.
    """
    name = blueprint.name
    return "stack_templates/%s/%s-%s.json" % (blueprint.context.get_fqn(name),
                                              name,
                                              blueprint.version)


def stack_template_url(bucket_name, blueprint, endpoint):
    """Produces an s3 url for a given blueprint.

    Args:
        bucket_name (string): The name of the S3 bucket where the resulting
            templates are stored.
        blueprint (:class:`stacker.blueprints.base.Blueprint`): The blueprint
            object to create the URL to.
        endpoint (string): The s3 endpoint used for the bucket.

    Returns:
        string: S3 URL.
    """
    key_name = stack_template_key_name(blueprint)
    return "%s/%s/%s" % (endpoint, bucket_name, key_name)


class BaseAction(object):

    """Actions perform the actual work of each Command.

    Each action is tied to a :class:`stacker.commands.base.BaseCommand`, and
    is responsible for building the :class:`stacker.plan.Plan` that will be
    executed to perform that command.

    Args:
        context (:class:`stacker.context.Context`): The stacker context for
            the current run.
        provider_builder (:class:`stacker.providers.base.BaseProviderBuilder`,
            optional): An object that will build a provider that will be
            interacted with in order to perform the necessary actions.
    """

    def __init__(self, context, provider_builder=None, cancel=None):
        self.context = context
        self.provider_builder = provider_builder
        self.bucket_name = context.bucket_name
        self.cancel = cancel or threading.Event()
        self.bucket_region = context.config.stacker_bucket_region
        if not self.bucket_region and provider_builder:
            self.bucket_region = provider_builder.region
        self.s3_conn = get_session(self.bucket_region).client('s3')

    def ensure_cfn_bucket(self):
        """The CloudFormation bucket where templates will be stored."""
        if self.bucket_name:
            ensure_s3_bucket(self.s3_conn,
                             self.bucket_name,
                             self.bucket_region)

    def stack_template_url(self, blueprint):
        return stack_template_url(
            self.bucket_name, blueprint, get_s3_endpoint(self.s3_conn)
        )

    def s3_stack_push(self, blueprint, force=False):
        """Pushes the rendered blueprint's template to S3.

        Verifies that the template doesn't already exist in S3 before
        pushing.

        Returns the URL to the template in S3.
        """
        key_name = stack_template_key_name(blueprint)
        template_url = self.stack_template_url(blueprint)
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
        try:
            self.pre_run(*args, **kwargs)
            self.run(*args, **kwargs)
            self.post_run(*args, **kwargs)
        except PlanFailed as e:
            logger.error(str(e))
            sys.exit(1)

    def pre_run(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        raise NotImplementedError("Subclass must implement \"run\" method")

    def post_run(self, *args, **kwargs):
        pass

    def build_provider(self, stack):
        """Builds a :class:`stacker.providers.base.Provider` suitable for
        operating on the given :class:`stacker.Stack`."""
        return self.provider_builder.build(region=stack.region,
                                           profile=stack.profile)

    @property
    def provider(self):
        """Some actions need a generic provider using the default region (e.g.
        hooks)."""
        return self.provider_builder.build()

    def _tail_stack(self, stack, cancel, retries=0, **kwargs):
        provider = self.build_provider(stack)
        return provider.tail_stack(stack, cancel, retries, **kwargs)
