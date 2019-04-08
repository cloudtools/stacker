from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import os
import logging
import time
import uuid
import threading

from .stack import Stack
from .util import stack_template_key_name
from .exceptions import (
    GraphError,
    PlanFailed,
)
from .ui import ui
from .dag import DAG, DAGValidationError, walk
from .status import (
    FailedStatus,
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED,
    FAILED,
)

logger = logging.getLogger(__name__)

COLOR_CODES = {
    SUBMITTED.code: 33,  # yellow
    COMPLETE.code: 32,   # green
    FAILED.code: 31,     # red
}


def log_step(step):
    msg = "%s: %s" % (step, step.status.name)
    if step.status.reason:
        msg += " (%s)" % (step.status.reason)
    color_code = COLOR_CODES.get(step.status.code, 37)
    ui.info(msg, extra={"color": color_code})


class Step(object):
    """State machine for executing generic actions related to stacks.

    Args:
        subject: the subject associated with this
            step. Usually a :class:`stacker.stack.Stack`,
                :class:`stacker.target.Target` or :class:`stacker.hooks.Hook`
        fn (funcb): the function to run to execute the step. This function
            will be ran multiple times until the step is "done".
        watch_func (func): an optional function that will be called to
            monitor the step action.
    """

    @classmethod
    def from_stack(cls, stack, fn, **kwargs):
        kwargs.setdefault('logging', stack.logging)
        return cls(stack.name, subject=stack, fn=fn, **kwargs)

    @classmethod
    def from_target(cls, target, fn, **kwargs):
        kwargs.setdefault('logging', True)
        return cls(target.name, subject=target, fn=fn, **kwargs)

    @classmethod
    def from_hook(cls, hook, fn, **kwargs):
        kwargs.setdefault('logging', True)
        return cls(hook.name, subject=hook, fn=fn, **kwargs)

    def __init__(self, name, fn, subject=None, watch_func=None, requires=None,
                 required_by=None, logging=False):
        self.name = name
        self.subject = subject
        self.fn = fn

        self.watch_func = watch_func
        self.requires = set(requires or [])
        self.required_by = set(required_by or [])
        if subject is not None:
            self.requires.update(subject.requires or [])
            self.required_by.update(subject.required_by or [])
        self.logging = logging

        self.status = PENDING
        self.last_updated = time.time()

    def __repr__(self):
        return "<stacker.plan.Step:%s>" % (self.name,)

    def __str__(self):
        return self.name

    def run(self):
        """Runs this step until it has completed successfully, or been
        skipped.
        """

        stop_watcher = threading.Event()
        watcher = None
        if self.watch_func:
            watcher = threading.Thread(
                target=self.watch_func,
                args=(self.subject, stop_watcher)
            )
            watcher.start()

        try:
            while not self.done:
                self._run_once()
        finally:
            if watcher:
                stop_watcher.set()
                watcher.join()
        return self.ok

    def _run_once(self):
        try:
            status = self.fn(self.subject, status=self.status)
        except Exception as e:
            logger.exception(e)
            status = FailedStatus(reason=str(e))
        self.set_status(status)
        return status

    @property
    def completed(self):
        """Returns True if the step is in a COMPLETE state."""
        return self.status == COMPLETE

    @property
    def skipped(self):
        """Returns True if the step is in a SKIPPED state."""
        return self.status == SKIPPED

    @property
    def failed(self):
        """Returns True if the step is in a FAILED state."""
        return self.status == FAILED

    @property
    def done(self):
        """Whether this step is finished (either COMPLETE, SKIPPED or FAILED)
        """
        return self.completed or self.skipped or self.failed

    @property
    def ok(self):
        """Whether this step is finished (either COMPLETE or SKIPPED)"""
        return self.completed or self.skipped

    @property
    def submitted(self):
        """Whether this step is has been submitted (SUBMITTED, COMPLETE, or
           SKIPPED).
        """
        return self.status >= SUBMITTED

    def set_status(self, status):
        """Sets the current step's status.
        Args:
            status (:class:`Status <Status>` object): The status to set the
                step to.
        """
        if status is not self.status:
            logger.debug("Setting %s state to %s.", self.name, status.name)
            self.status = status
            self.last_updated = time.time()
            if self.logging:
                log_step(self)

    def complete(self):
        """A shortcut for set_status(COMPLETE)"""
        self.set_status(COMPLETE)

    def skip(self):
        """A shortcut for set_status(SKIPPED)"""
        self.set_status(SKIPPED)

    def submit(self):
        """A shortcut for set_status(SUBMITTED)"""
        self.set_status(SUBMITTED)

    def reverse_requirements(self):
        """
        Change this step so it is suitable for use in operations in reverse
        dependency order.

        This can be used to correctly generate an action graph when destroying
        stacks.
        """
        self.required_by, self.requires = self.requires, self.required_by


class Graph(object):
    """Graph represents a graph of steps.

    The :class:`Graph` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. When initialized
    with a set of steps, it will first build a Directed Acyclic Graph from the
    steps and their dependencies.

    Example:

    >>> dag = DAG()
    >>> def build(*args, **kwargs): return COMPLETE
    >>> a = Step("a", fn=build)
    >>> b = Step("b", fn=build)
    >>> dag.add_step(a)
    >>> dag.add_step(b)
    >>> dag.connect(a, b)

    Args:
        steps (dict): an optional list of :class:`Step` objects to execute.
        dag (:class:`stacker.dag.DAG`): an optional :class:`stacker.dag.DAG`
            object. If one is not provided, a new one will be initialized.
    """

    @classmethod
    def from_steps(cls, steps):
        """Builds a graph of steps respecting dependencies

        Args:
            steps (List[Step]): steps to include in the graph
        Returns: :class:`Graph`: the resulting graph
        """

        graph = Graph()

        for step in steps:
            graph.add_step(step)

        for step in steps:
            for dep in step.requires:
                graph.connect(step.name, dep)

            for parent in step.required_by:
                graph.connect(parent, step.name)

        return graph

    def __init__(self, steps=None, dag=None):
        self.steps = steps or {}
        self.dag = dag or DAG()

    def add_step(self, step):
        self.steps[step.name] = step
        self.dag.add_node(step.name)

    def connect(self, step, dep):
        try:
            self.dag.add_edge(step, dep)
        except KeyError as e:
            raise GraphError(e, step, dep)
        except DAGValidationError as e:
            raise GraphError(e, step, dep)

    def transitive_reduction(self):
        self.dag.transitive_reduction()

    def walk(self, walker, walk_func):
        def fn(step_name):
            step = self.steps[step_name]
            return walk_func(step)

        return walker(self.dag, fn)

    def downstream(self, step_name):
        """Returns the direct dependencies of the given step"""
        return list(self.steps[dep] for dep in self.dag.downstream(step_name))

    def transposed(self):
        """Returns a "transposed" version of this graph. Useful for walking in
        reverse.
        """
        return Graph(steps=self.steps, dag=self.dag.transpose())

    def filtered(self, step_names):
        """Returns a "filtered" version of this graph."""
        return Graph(steps=self.steps, dag=self.dag.filter(step_names))

    def topological_sort(self):
        nodes = self.dag.topological_sort()
        return [self.steps[step_name] for step_name in nodes]

    def get(self, name, default=None):
        return self.steps.get(name, default)

    def to_dict(self):
        return self.dag.graph


class Plan(object):
    """A convenience class for working on a Graph.
    Args:
        description (str): description of the plan.
        graph (:class:`Graph`): a graph of steps.
    """

    @classmethod
    def from_graph(cls, description, graph, targets=None):
        """Builds a plan from a list of steps.

        Args:
            description (str): an arbitrary string to describe the plan.
            graph (Graph): a :class:`Graph` to base the plan on
            targets (list, optional): names of steps to include in the graph.
                If provided, only these steps, and their transitive
                dependencies will be executed. Otherwise, every node in the
                graph will be executed.
        Returns: Plan: the resulting plan
        """

        # If we only want to build a specific target, filter the graph.
        if targets:
            graph = graph.filtered(targets)

        return Plan(description=description, graph=graph)

    def __init__(self, description, graph):
        self.id = uuid.uuid4()
        self.description = description
        self.graph = graph

    def outline(self, level=logging.INFO, message=""):
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
        logger.log(level, "Plan \"%s\":", self.description)
        for step in self.steps:
            logger.log(
                level,
                "  - step: %s: target: \"%s\", action: \"%s\"",
                steps,
                step.name,
                step.fn.__name__,
            )
            steps += 1

        if message:
            logger.log(level, message)

    def dump(self, directory, context, provider=None):
        logger.info("Dumping \"%s\"...", self.description)
        directory = os.path.expanduser(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)

        def walk_func(step):
            if not isinstance(step.subject, Stack):
                return True

            step.subject.resolve(
                context=context,
                provider=provider,
            )
            blueprint = step.subject.blueprint
            filename = stack_template_key_name(blueprint)
            path = os.path.join(directory, filename)

            blueprint_dir = os.path.dirname(path)
            if not os.path.exists(blueprint_dir):
                os.makedirs(blueprint_dir)

            logger.info("Writing stack \"%s\" -> %s", step.name, path)
            with open(path, "w") as f:
                f.write(blueprint.rendered)

            return True

        return self.graph.walk(walk, walk_func)

    def execute(self, *args, **kwargs):
        """Walks each step in the underlying graph, and raises an exception if
        any of the steps fail.

        Raises:
            PlanFailed: Raised if any of the steps fail.
        """
        self.walk(*args, **kwargs)

        failed_steps = [step for step in self.steps if step.status == FAILED]
        if failed_steps:
            raise PlanFailed(failed_steps)

    def walk(self, walker):
        """Walks each step in the underlying graph, in topological order.

        Args:
            walker (func): a walker function to be passed to
                :class:`stacker.dag.DAG` to walk the graph.
        """

        def walk_func(step):
            # Before we execute the step, we need to ensure that it's
            # transitive dependencies are all in an "ok" state. If not, we
            # won't execute this step.
            for dep in self.graph.downstream(step.name):
                if not dep.ok:
                    step.set_status(FailedStatus("dependency has failed"))
                    return step.ok

            return step.run()

        return self.graph.walk(walker, walk_func)

    @property
    def steps(self):
        steps = self.graph.topological_sort()
        steps.reverse()
        return steps

    @property
    def step_names(self):
        return [step.name for step in self.steps]

    def keys(self):
        return self.step_names

    def get(self, name, default=None):
        for step in self.steps:
            if step.name == name:
                return step

        return default
