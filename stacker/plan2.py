import os
import logging
import time
import uuid
import multiprocessing

from colorama.ansi import Fore

from .util import stack_template_key_name
from .exceptions import (
    GraphError,
)
from .dag import DAG, DAGValidationError
from .status import (
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED,
    FAILED,
)

logger = logging.getLogger(__name__)


class Step(object):
    """State machine for executing generic actions related to stacks.
    Args:
        stack (:class:`stacker.stack.Stack`): the stack associated
            with this step
        fn (func): the function to run to execute the step. This function will
            be ran multiple times until the step is "done".
        watch_func (func): an optional function that will be called to "tail"
            the step action.
        status_changed_func (func): an optional function that will be called
            when the step changes status.
    """

    def __init__(self, stack, fn, watch_func=None,
                 status_changed_func=None):
        self.stack = stack
        self.status = PENDING
        self.last_updated = time.time()
        self.fn = fn
        self.watch_func = watch_func
        self.status_changed_func = status_changed_func

    def __repr__(self):
        return "<stacker.plan.Step:%s>" % (self.stack.fqn,)

    def run(self):
        """Runs this step until it has completed successfully, or been
        skipped.
        """

        watcher = None
        if self.watch_func:
            watcher = multiprocessing.Process(
                target=self.watch_func,
                args=(self.stack,)
            )
            watcher.start()

        try:
            if self.status_changed_func:
                self.status_changed_func()

            while not self.done:
                self._run_once()
        finally:
            if watcher and watcher.is_alive():
                watcher.terminate()
                watcher.join()
        return self.ok

    def _run_once(self):
        status = self.fn(self.stack, status=self.status)
        self.set_status(status)
        return status

    @property
    def name(self):
        return self.stack.fqn

    @property
    def short_name(self):
        return self.stack.name

    @property
    def requires(self):
        return self.stack.requires

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
        """Returns True if the step is finished (either COMPLETE, SKIPPED or FAILED)
        """
        return self.completed or self.skipped or self.failed

    @property
    def ok(self):
        """Returns True if the step is finished (either COMPLETE or SKIPPED)"""
        return self.completed or self.skipped

    @property
    def submitted(self):
        """Returns True if the step is SUBMITTED, COMPLETE, or SKIPPED."""
        return self.status >= SUBMITTED

    def set_status(self, status):
        """Sets the current step's status.
        Args:
            status (:class:`Status <Status>` object): The status to set the
                step to.
        """
        if status is not self.status:
            logger.debug("Setting %s state to %s.", self.stack.name,
                         status.name)
            self.status = status
            self.last_updated = time.time()
            if self.status_changed_func:
                self.status_changed_func()

    def complete(self):
        """A shortcut for set_status(COMPLETE)"""
        self.set_status(COMPLETE)

    def skip(self):
        """A shortcut for set_status(SKIPPED)"""
        self.set_status(SKIPPED)

    def submit(self):
        """A shortcut for set_status(SUBMITTED)"""
        self.set_status(SUBMITTED)


def build_plan(description, steps,
               targets=None, reverse=False):
    """Builds a plan from a list of steps.
    Args:
        description (str): an arbitrary string to
            describe the plan.
        steps (list): a list of :class:`Step` objects to execute.
        targets (list): an optional list of step names to filter the graph to.
            If provided, only these steps, and their transitive dependencies
            will be executed. If no targets are specified, every node in the
            graph will be executed.
        reverse (bool): If provided, the graph will be walked in reverse order
            (dependencies last).
    """
    graph = build_graph(steps)

    # If we want to execute the plan in reverse (e.g. Destroy), transpose the
    # graph.
    if reverse:
        graph = graph.transposed()

    # If we only want to build a specific target, filter the graph.
    if targets:
        nodes = []
        for target in targets:
            for step in steps:
                if step.short_name == target:
                    nodes.append(step.name)
        graph = graph.filtered(nodes)

    return Plan(description=description, graph=graph)


def build_graph(steps):
    """Builds a graph of steps.
    Args:
        steps (list): a list of :class:`Step` objects to execute.
    """

    graph = Graph()

    for step in steps:
        graph.add_step(step)

    for step in steps:
        for dep in step.requires:
            graph.connect(step, dep)

    return graph


class Graph(object):
    """Graph represents a graph of steps.

    The :class:`Graph` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. When initialized
    with a set of steps, it will first build a Directed Acyclic Graph from the
    steps and their dependencies.

    Example:

    >>> dag = DAG()
    >>> a = Step("a", fn=build)
    >>> b = Step("b", fn=build)
    >>> dag.add_step(a)
    >>> dag.add_step(b)
    >>> dag.connect(a, b)

    Args:
        steps (list): an optional list of :class:`Step` objects to execute.
        dag (:class:`stacker.dag.DAG`): an optional :class:`stacker.dag.DAG`
            object. If one is not provided, a new one will be initialized.
    """

    def __init__(self, steps=None, dag=None):
        self.steps = steps or {}
        self.dag = dag or DAG()

    def add_step(self, step):
        self.steps[step.name] = step
        self.dag.add_node(step.name)

    def connect(self, step, dep):
        try:
            self.dag.add_edge(step.name, dep)
        except KeyError as e:
            raise GraphError(e, step.name, dep)
        except DAGValidationError as e:
            raise GraphError(e, step.name, dep)

    def walk(self, walk_func):
        def fn(step_name):
            step = self.steps[step_name]
            return walk_func(step)

        return self.dag.walk(fn)

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

    def to_dict(self):
        return self.dag.graph


class Plan(object):
    """A convenience class for working on a Graph.
    Args:
        description (str): description of the plan.
        graph (:class:`Graph`): a graph of steps.
    """

    def __init__(self, description=None, graph=None):
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
                step.short_name,
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
            step.stack.resolve(
                context=context,
                provider=provider,
            )
            blueprint = step.stack.blueprint
            filename = stack_template_key_name(blueprint)
            path = os.path.join(directory, filename)

            blueprint_dir = os.path.dirname(path)
            if not os.path.exists(blueprint_dir):
                os.makedirs(blueprint_dir)

            logger.info("Writing stack \"%s\" -> %s", step.name, path)
            with open(path, "w") as f:
                f.write(blueprint.rendered)

            return True

        return self.graph.walk(walk_func)

    def execute(self, **kwargs):
        return self.walk(**kwargs)

    def walk(self):
        """Walks each step in the underlying graph, in topological order."""

        def walk_func(step):
            return step.run()

        return self.graph.walk(walk_func)

    def _check_point(self):
        """Outputs the current status of all steps in the plan."""
        status_to_color = {
            SUBMITTED.code: Fore.YELLOW,
            COMPLETE.code: Fore.GREEN,
        }
        logger.info("Plan Status:", extra={"reset": True, "loop": self.id})

        longest = 0
        messages = []
        for step in self.steps:
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
                'loop': self.id,
                'color': color,
                'last_updated': step.last_updated,
            })

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
