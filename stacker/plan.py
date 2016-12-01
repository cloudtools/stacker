import logging
import os
import time
import uuid

from colorama.ansi import Fore

from .exceptions import (
    CyclicDependencyError,
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


class Plan():
    def __init__(self, description, reverse=False, sleep_func=sleep):
        self.description = description
        self._dag = None
        self._steps = {}
        self._reverse = reverse
        self._sleep_func = sleep_func
        self.id = uuid.uuid4()

    def build(self, stacks):
        """ Builds an internal dag from the stacks and their dependencies """
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
                except DAGValidationError:
                    raise CyclicDependencyError(stack.fqn)

        self._dag = dag
        return None

    def execute(self, fn):
        """ Executes the plan by walking the graph and executing dependencies
        first.
        """
        check_point = self._check_point
        sleep_func = self._sleep_func

        # This function is called for each step in the graph, it's responsible
        # for managing the lifecycle of the step until completion.
        def step_func(step):
            while not step.done:
                check_point()
                status = fn(step.stack, status=step.status)
                step.set_status(status)
                check_point()
                if sleep_func:
                    sleep_func()

        self._walk_steps(step_func)
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

    def to_dot(self):
        return self._dag.to_dot()

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

    def _walk_steps(self, step_func):
        steps = self._steps

        def walk_func(fqn):
            step = steps[fqn]
            step_func(step)

        reverse = True
        if self._reverse:
            reverse = False

        return self._dag.walk(walk_func, reverse=reverse)

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
