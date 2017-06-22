import logging
import time
import uuid

from .exceptions import (
    GraphError,
)
from .dag import DAG, DAGValidationError
from .status import (
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED,
    CANCELLED,
    ERRORED,
    ErroredStatus
)

logger = logging.getLogger(__name__)


class Step(object):
    """State machine for executing generic actions related to stacks.

    Args:
        stack (:class:`stacker.stack.Stack`): the stack associated
            with this step

    """

    def __init__(self, stack, fn=None, check_point=None):
        self.stack = stack
        self.status = PENDING
        self.last_updated = time.time()
        self.fn = fn
        self.check_point = check_point

    def __repr__(self):
        return "<stacker.plan.Step:%s>" % (self.stack.fqn,)

    def run(self):
        """Runs this step until it has completed successfully, or been
        skipped.
        """

        while not self.done:
            try:
                status = self.fn(self)
                self.set_status(status)
            except Exception as e:
                self.set_status(ErroredStatus(e.message))
        return self.ok

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
    def cancelled(self):
        """Returns True if the step is in a CANCELLED state."""
        return self.status == CANCELLED

    @property
    def errored(self):
        """Returns True if the step is in a ERRORED state."""
        return self.status == ERRORED

    @property
    def done(self):
        """Returns True if the step is finished (either COMPLETE, SKIPPED or
        CANCELLED)
        """
        return self.completed or self.skipped or self.cancelled or self.errored

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
            if self.check_point:
                self.check_point()
            self.status = status
            self.last_updated = time.time()

    def complete(self):
        """A shortcut for set_status(COMPLETE)"""
        self.set_status(COMPLETE)

    def skip(self):
        """A shortcut for set_status(SKIPPED)"""
        self.set_status(SKIPPED)

    def submit(self):
        """A shortcut for set_status(SUBMITTED)"""
        self.set_status(SUBMITTED)


def build_plan(description=None, steps=None,
               step_names=None, reverse=False,
               check_point=None):
    graph = build_graph(steps)

    # If we want to execute the plan in reverse (e.g. Destroy), transpose the
    # graph.
    if reverse:
        graph = graph.transposed()

    # If we only want to build a specific target, filter the graph.
    if step_names:
        nodes = []
        for step_name in step_names:
            for step in steps:
                if step.short_name == step_name:
                    nodes.append(step.name)
        graph = graph.filtered(nodes)

    return Plan(description=description, graph=graph, check_point=check_point)


class Plan(object):
    """A collection of :class:`Step` objects to execute.

    The :class:`Plan` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. When initialized
    with a set of steps, it will first build a Directed Acyclic Graph from the
    steps and their dependencies.

    Args:
        description (str): description of the plan.
        graph (:class:`Graph`): a graph of steps.
        check_point (func): a function to call whenever steps change status.

    """

    def __init__(self, description=None, graph=None, check_point=None):
        self.id = uuid.uuid4()
        self.description = description
        self.check_point = check_point or null_check_point

        if check_point:
            def _check_point():
                check_point(self)

            for step_name, step in graph.steps.iteritems():
                step.check_point = _check_point

        self.graph = graph

    def execute(self, **kwargs):
        self.check_point(self)
        ret = self.walk(**kwargs)
        self.check_point(self)
        return ret

    def walk(self, semaphore=None):
        """Walks each step in the underlying graph, in topological order.

        Args:
            step_func (func): a function that will be called with the step.
            semaphore (threading.Semaphore, option): a semaphore object which
                can be used to control how many steps are executed in parallel.
                By default, there is not limit to the amount of parallelism,
                other than what the graph topology allows.

        """

        if not semaphore:
            semaphore = UnlimitedSemaphore()

        def walk_func(step):
            semaphore.acquire()
            try:
                return step.run()
            finally:
                semaphore.release()

        return self.graph.walk(walk_func)

    @property
    def steps(self):
        steps = self.graph.topological_sort()
        steps.reverse()
        return steps

    @property
    def step_names(self):
        return [step.name for step in self.steps]


def null_check_point(plan):
    pass


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
    """Graph represents a graph of steps."""

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


class UnlimitedSemaphore(object):
    """UnlimitedSemaphore implements the same interface as threading.Semaphore,
    but acquire's always succeed.
    """

    def acquire(self, *args):
        pass

    def release(self):
        pass
