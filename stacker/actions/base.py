from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import os
import sys
import logging
import threading

from ..dag import walk, ThreadedWalker, UnlimitedSemaphore
from ..plan import Graph, Plan, Step, merge_graphs

import botocore.exceptions
from stacker.session_cache import get_session
from stacker.exceptions import PlanFailed

from ..status import (
    COMPLETE
)

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

    semaphore = UnlimitedSemaphore()
    if concurrency > 1:
        semaphore = threading.Semaphore(concurrency)

    return ThreadedWalker(semaphore).walk


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

    DESCRIPTION = 'Base action'

    def __init__(self, context, provider_builder=None, cancel=None):
        self.context = context
        self.provider_builder = provider_builder
        self.bucket_name = context.bucket_name
        self.cancel = cancel or threading.Event()
        self.bucket_region = context.config.stacker_bucket_region
        if not self.bucket_region and provider_builder:
            self.bucket_region = provider_builder.region
        self.s3_conn = (getattr(self.context, 's3_conn', None) or
                        get_session(self.bucket_region).client('s3'))

    @property
    def _stack_action(self):
        """The function run against a step."""
        raise NotImplementedError

    @property
    def provider(self):
        """Some actions need a generic provider using the default region (e.g.
        hooks)."""
        return self.provider_builder.build()

    def _generate_plan(self, tail=False, reverse=False,
                       require_unlocked=True,
                       include_persistent_graph=False):
        """Create a plan for this action.

        Args:
            tail (Union[bool, Callable]): An optional function to call
                to tail the stack progress.
            reverse (bool): If True, execute the graph in reverse (useful for
                destroy actions).
            require_unlocked (bool): If the persistent graph is locked, an
                error is raised.
            include_persistent_graph (bool): Include the persistent graph
                in the :class:`stacker.plan.Plan` (if there is one).
                This will handle basic merging of the local and persistent
                graphs if an action does not require more complex logic.

        Returns:
            :class:`stacker.plan.Plan`: The resulting plan object

        """
        tail = self._tail_stack if tail else None

        def target_fn(*args, **kwargs):
            return COMPLETE

        steps = [
            Step(stack, fn=self._stack_action, watch_func=tail)
            for stack in self.context.get_stacks()]

        steps += [
            Step(target, fn=target_fn)
            for target in self.context.get_targets()]

        graph = Graph.from_steps(steps)

        if include_persistent_graph and self.context.persistent_graph:
            persist_steps = Step.from_persistent_graph(
                self.context.persistent_graph.to_dict(),
                self.context,
                fn=self._stack_action,
                watch_func=tail
            )
            persist_graph = Graph.from_steps(persist_steps)
            graph = merge_graphs(graph, persist_graph)

        return Plan(
            context=self.context,
            description=self.DESCRIPTION,
            graph=graph,
            reverse=reverse,
            require_unlocked=require_unlocked)

    def _tail_stack(self, stack, cancel, retries=0, **kwargs):
        provider = self.build_provider(stack)
        return provider.tail_stack(stack, cancel, retries, **kwargs)

    def build_provider(self, stack):
        """Builds a :class:`stacker.providers.base.Provider` suitable for
        operating on the given :class:`stacker.Stack`."""
        return self.provider_builder.build(region=stack.region,
                                           profile=stack.profile)

    def ensure_cfn_bucket(self):
        """The CloudFormation bucket where templates will be stored."""
        if not self.context.s3_bucket_verified and self.bucket_name:
            ensure_s3_bucket(self.s3_conn,
                             self.bucket_name,
                             self.bucket_region)

    def execute(self, *args, **kwargs):
        try:
            self.pre_run(*args, **kwargs)
            self.run(*args, **kwargs)
            self.post_run(*args, **kwargs)
        except PlanFailed as e:
            logger.error(str(e))
            sys.exit(1)

    def post_run(self, *args, **kwargs):
        pass

    def pre_run(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        raise NotImplementedError("Subclass must implement \"run\" method")

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
                                ServerSideEncryption='AES256',
                                ACL='bucket-owner-full-control')
        logger.debug("Blueprint %s pushed to %s.", blueprint.name,
                     template_url)
        return template_url

    def stack_template_url(self, blueprint):
        return stack_template_url(
            self.bucket_name, blueprint, get_s3_endpoint(self.s3_conn)
        )
