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
    CANCELLED
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
            status = self.fn(self)
            self.set_status(status)
        return self.ok

    @property
    def name(self):
        return self.stack.fqn

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
    def done(self):
        """Returns True if the step is finished (either COMPLETE, SKIPPED or
        CANCELLED)
        """
        return self.completed or self.skipped or self.cancelled

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


class Plan(object):
    """A collection of :class:`Step` objects to execute.

    The :class:`Plan` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. When initialized
    with a set of steps, it will first build a Directed Acyclic Graph from the
    steps and their dependencies.

    Args:
        description (str): description of the plan
        steps (list): a list of :class:`Step` objects to execute.
        reverse (bool, optional): by default, the plan will be run in
            topological order based on each steps dependencies. Put
            more simply, the steps with no dependencies will be ran
            first. When this flag is set, the plan will be executed
            in reverse order.

    """

    def __init__(self, description=None, steps=None,
                 reverse=False, check_point=None):
        self.id = uuid.uuid4()
        self.description = description
        self.check_point = check_point or null_check_point

        if check_point:
            def _check_point():
                check_point(self)

            for step in steps:
                step.check_point = _check_point

        self.steps = {step.name: step for step in steps}
        self.dag = build_dag(steps)
        if reverse:
            self.dag = self.dag.transpose()

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

        def walk_func(step_name):
            step = self.steps[step_name]
            semaphore.acquire()
            try:
                return step.run()
            finally:
                semaphore.release()

        return self.dag.walk(walk_func)

    def keys(self):
        return [k for k in self.steps]


def null_check_point(plan):
    pass


def build_dag(steps):
    """Builds a Directed Acyclic Graph, given a list of steps.

    Args:
        steps (list): a list of :class:`Step` objects to execute.

    """

    dag = DAG()

    for step in steps:
        dag.add_node(step.name)

    for step in steps:
        for dep in step.requires:
            try:
                dag.add_edge(step.name, dep)
            except KeyError as e:
                raise GraphError(e, step.name, dep)
            except DAGValidationError as e:
                raise GraphError(e, step.name, dep)

    return dag


class UnlimitedSemaphore(object):
    """UnlimitedSemaphore implements the same interface as threading.Semaphore,
    but acquire's always succeed.
    """

    def acquire(self, *args):
        pass

    def release(self):
        pass
