from collections import OrderedDict
import hashlib
import logging
import os
import time
import uuid

from colorama.ansi import Fore


from .actions.base import stack_template_key_name
from .exceptions import (
    CancelExecution
)
from .logger import LOOP_LOGGER_TYPE
from .status import (
    SkippedStatus,
    Status,
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED
)

logger = logging.getLogger(__name__)


class Step(object):

    """State machine for executing generic actions related to stacks.

    Args:
        stack (:class:`stacker.stack.Stack`): the stack associated
            with this step
        run_func (func): the function to be run for the given stack
        requires (list, optional): List of stacks this step depends on being
            completed before running. This step will not be executed unless the
            required stacks have either completed or skipped.

    """

    def __init__(self, stack, run_func, requires=None):
        self.stack = stack
        self.status = PENDING
        self.requires = requires or []
        self._run_func = run_func
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

    def run(self):
        return self._run_func(self.stack, status=self.status)

    def set_status(self, status):
        """Sets the current step's status.

        Args:
            status (:class:`Status <Status>` object): The status to set the
                step to.
        """
        if not isinstance(status, Status):
            raise ValueError(
                "Invalid status type: %s - must be subclass of "
                "stacker.status.Status class. " % type(status)
            )

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


class Plan(OrderedDict):

    """A collection of :class:`Step` objects to execute.

    The :class:`Plan` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. It will run the
    steps in the order they are added to the `Plan` via the :func:`Plan.add`
    function. If a `Step` specifies requirements, the `Plan` will wait until
    the required stacks have completed before executing that `Step`.

    Args:
        description (str): description of the plan
        tail(bool): Enable this to true if you want the Plan to output
            every event that it recieves.
        poll_func(function): The function for polling for new events about the
            stacks. Returns a dict with the the keys of the dict representing
            the name of the Stack and the value representing the status.

    """

    def __init__(self, description, tail=False, logger_type=None,
                 poll_func=None, *args, **kwargs):
        self.description = description
        self.logger_type = logger_type
        self.tail = tail
        self.id = uuid.uuid4()
        self._poll_func = poll_func
        super(Plan, self).__init__(*args, **kwargs)

    def add(self, stack, run_func, requires=None):
        """Add a new step to the plan.

        Args:
            stack (:class:`stacker.stack.Stack`): The stack to add to the plan.
            run_func (function): The function to call when the step is ran.
            requires (list, optional): A list of other stacks that are required
                to be complete before this step is started.
        """
        self[stack.fqn] = Step(
            stack=stack,
            run_func=run_func,
            requires=requires
        )

    def poll(self):
        stack_dict = self._poll_func(self.tail)
        for step_name, step in self.list_pending():
            if step_name in stack_dict:
                status = stack_dict[step_name]
                step.set_status(status)

    def list_status(self, status):
        """Returns a list of steps in the given status.

        Args:
            status (:class:`Status`): The status to match steps against.

        Returns:
            list: A list of :class:`Step` objects that are in the given status.
        """
        return [step for step in self.iteritems() if step[1].status == status]

    def list_completed(self):
        """A shortcut for list_status(COMPLETE)"""
        return self.list_status(COMPLETE)

    def list_submitted(self):
        """A shortcut for list_status(SUBMITTED)"""
        return self.list_status(SUBMITTED)

    def list_skipped(self):
        """A shortcut for list_status(SKIPPED)"""
        return self.list_status(SKIPPED)

    def list_pending(self):
        """Pending is any task that isn't COMPLETE or SKIPPED. """
        return [step for step in self.iteritems() if (
            step[1].status != COMPLETE and
            step[1].status != SKIPPED
        )]

    @property
    def check_point_interval(self):
        return 1 if self.logger_type == LOOP_LOGGER_TYPE else 10

    @property
    def completed(self):
        """True if there are no more pending steps."""
        if self.list_pending():
            return False
        return True

    def _single_run(self):
        """Executes a single run through the plan, touching each step."""
        for step_name, step in self.list_pending():
            waiting_on = []
            for required_stack in step.requires:
                if not self[required_stack].completed and \
                        not self[required_stack].skipped:
                    waiting_on.append(required_stack)

            if waiting_on:
                logger.debug(
                    "Stack: \"%s\" waiting on required stacks: %s",
                    step.stack.name,
                    ", ".join(waiting_on),
                )
                continue

            if not step.submitted:
                try:
                    status = step.run()
                except CancelExecution:
                    status = SkippedStatus(reason="canceled execution")
                step.set_status(status)
            else:
                self.poll()

    def execute(self):
        """Execute the plan.

        This will run through all of the steps registered with the plan and
        submit them in parallel based on their dependencies.
        """
        attempts = 0
        last_md5 = self.md5

        while not self.completed:
            if (not attempts % self.check_point_interval or
                    self.md5 != last_md5):
                last_md5 = self.md5
                self._check_point()
            attempts += 1
            self._single_run()

        self._check_point()

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
        while not self.completed:
            step_name, step = self.list_pending()[0]
            logger.log(
                level,
                "  - step: %s: target: \"%s\", action: \"%s\"",
                steps,
                step_name,
                step._run_func.__name__,
            )
            # Set the status to COMPLETE directly so we don't call the
            # completion func
            step.status = COMPLETE
            steps += 1

        if message:
            logger.log(level, message)

        self.reset()

    def reset(self):
        for _, step in self.iteritems():
            step.status = PENDING

    def dump(self, directory, context):
        steps = 1
        logger.info("Dumping \"%s\"...", self.description)
        directory = os.path.expanduser(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)

        while not self.completed:
            step_name, step = self.list_pending()[0]
            step.stack.resolve(
                context=context,
                provider=None,
            )
            blueprint = step.stack.blueprint
            filename = stack_template_key_name(blueprint)
            path = os.path.join(directory, filename)
            logger.info("Writing stack \"%s\" -> %s", step_name, path)
            with open(path, "w") as f:
                f.write(blueprint.rendered)

            step.status = COMPLETE
            steps += 1

        self.reset()

    @property
    def md5(self):
        """A hash for the plan's current state.

        This is useful if we want to determine if any of the plan's steps have
        changed during execution.

        """
        statuses = []
        for step_name, step in self.iteritems():
            current = '{}{}{}'.format(step_name, step.status.name,
                                      step.status.reason)
            statuses.append(current)
        return hashlib.md5(' '.join(statuses)).hexdigest()

    def _check_point(self):
        """Outputs the current status of all steps in the plan."""
        status_to_color = {
            SUBMITTED.code: Fore.YELLOW,
            COMPLETE.code: Fore.GREEN,
        }
        logger.info("Plan Status:", extra={"reset": True, "loop": self.id})

        longest = 0
        messages = []
        for step_name, step in self.iteritems():
            length = len(step_name)
            if length > longest:
                longest = length

            msg = "%s: %s" % (step_name, step.status.name)
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
