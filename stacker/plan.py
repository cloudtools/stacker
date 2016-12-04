import logging
import os
import time
import uuid
import threading

from colorama.ansi import Fore

from .exceptions import (
    GraphError,
)

from .dag import DAG, DAGValidationError
from .actions.base import stack_template_key_name

from .status import (
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED
)

logger = logging.getLogger(__name__)


def sleep():
    time.sleep(5)


class Step(object):
    """State machine for executing generic actions related to stacks.
    Args:
        stack (:class:`stacker.stack.Stack`): the stack associated
            with this step
    """

    def __init__(self, stack):
        self.stack = stack
        self.status = PENDING
        self.last_updated = time.time()

    def __repr__(self):
        return "<stacker.plan.Step:%s>" % (self.stack.fqn,)

    @property
    def completed(self):
        """Returns True if the step is in a COMPLETE state."""
        return self.status == COMPLETE

    @property
    def skipped(self):
        """Returns True if the step is in a SKIPPED state."""
        return self.status == SKIPPED

    @property
    def done(self):
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
    action for a set of :class:`stacker.stack.Stack` objects. Once a plan is
    initialized, :func:`Plan.build` should be called with a list of stacks
    to build the dependency graph. After the plan has been built, it can be
    executed via :func:`Plan.execute`.

    Args:
        description (str): description of the plan
        reverse (bool, optional): by default, the plan will be run in
            topological order based on each stacks dependencies. Put
            more simply, the stacks with no dependencies will be ran
            first. When this flag is set, the plan will be executed
            in reverse order. This can be useful for destroy actions.
        sleep_func (func, optional): when executing the plan, the
            provided function may be called multiple times. This
            controls the wait time between successive calls.
    """

    def __init__(self, description, reverse=False, sleep_func=sleep):
        self.description = description
        self._dag = None
        self._steps = {}
        self._reverse = reverse
        self._sleep_func = sleep_func
        self.id = uuid.uuid4()
        # Manages synchronization around calling `fn` within `execute`.
        self._lock = threading.Lock()

    def build(self, stacks, stack_names=None):
        """ Builds an internal dag from the stacks and their dependencies.

        Args:
            stacks (list): a list of :class:`stacker.stack.Stack` objects
                to build the plan with.
            stack_names (list): a list of stack names to filter on.
        """
        dag = DAG()

        for stack in stacks:
            fqn = stack.fqn
            dag.add_node(fqn)
            self._steps[fqn] = Step(
                stack=stack)

        for stack in stacks:
            for dep in stack.requires:
                try:
                    dag.add_edge(stack.fqn, dep)
                except KeyError as e:
                    raise GraphError(e, stack.fqn, dep)
                except DAGValidationError as e:
                    raise GraphError(e, stack.fqn, dep)

        if stack_names:
            nodes = []
            for stack_name in stack_names:
                for stack in stacks:
                    if stack.name == stack_name:
                        nodes.append(stack.fqn)
            dag = dag.filter(nodes)

        self._dag = dag
        return None

    def execute(self, fn, parallel=True, cancel=None):
        """ Executes the plan by walking the graph and executing dependencies
        first.

        Args:
            fn (func): a function that will be executed for each step. The
                function will be called multiple times until the step is
                `done`. The function should return a
                :class:`stacker.status.Status` each time it is called.
        """
        check_point = self._check_point
        sleep_func = self._sleep_func
        lock = self._lock

        check_point()

        # This function is called for each step in the graph, it's responsible
        # for managing the lifecycle of the step until completion.
        def step_func(step):
            while not step.done:
                lock.acquire()
                current_status = step.status
                status = fn(step.stack, status=step.status)
                step.set_status(status)
                if status != current_status:
                    check_point()
                lock.release()

                if sleep_func and not step.done:
                    sleep_func()

        self._walk_steps(step_func, parallel=parallel, cancel=cancel)
        return True

    def dump(self, directory):
        logger.info("Dumping \"%s\"...", self.description)
        directory = os.path.expanduser(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)

        def step_func(step):
            blueprint = step.stack.blueprint
            filename = stack_template_key_name(blueprint)
            path = os.path.join(directory, filename)
            logger.info("Writing stack \"%s\" -> %s", step.stack.fqn, path)
            with open(path, "w") as f:
                f.write(blueprint.rendered)

        self._walk_steps(step_func)

    def keys(self):
        return self._steps.keys()

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

        def step_func(step):
            logger.log(
                level,
                "  - step: %s: target: \"%s\"",
                steps,
                step.stack.fqn,
            )

        self._walk_steps(step_func)

        if message:
            logger.log(level, message)

    def _walk_steps(self, step_func, parallel=False, cancel=None):
        steps = self._steps

        def walk_func(fqn):
            step = steps[fqn]
            step_func(step)

        dag = self._dag
        if self._reverse:
            dag = dag.transpose()

        walk = dag.walk
        if parallel:
            walk = dag.walk_parallel

        return walk(walk_func, cancel=cancel)

    def _check_point(self):
        """Outputs the current status of all steps in the plan."""
        status_to_color = {
            SUBMITTED.code: Fore.YELLOW,
            COMPLETE.code: Fore.GREEN,
        }
        logger.info("Plan Status:", extra={"reset": True, "loop": self.id})

        class local:
            longest = 0
        messages = []

        def step_func(step):
            length = len(step.stack.fqn)
            if length > local.longest:
                local.longest = length

            msg = "%s: %s" % (step.stack.fqn, step.status.name)
            if step.status.reason:
                msg += " (%s)" % (step.status.reason)

            messages.append((msg, step))

        self._walk_steps(step_func)

        for msg, step in messages:
            parts = msg.split(' ', 1)
            fmt = "\t{0: <%d}{1}" % (local.longest + 2,)
            color = status_to_color.get(step.status.code, Fore.WHITE)
            logger.info(fmt.format(*parts), extra={
                'loop': self.id,
                'color': color,
                'last_updated': step.last_updated,
            })
