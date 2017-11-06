from collections import OrderedDict
import hashlib
import logging
import multiprocessing
import os
import time
import uuid

from colorama.ansi import Fore


from .actions.base import stack_template_key_name
from .exceptions import (
    CancelExecution,
    ImproperlyConfigured,
    PlanFailed
)
from .logger import LOOP_LOGGER_TYPE
from .status import (
    FailedStatus,
    SkippedStatus,
    Status,
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED,
    FAILED
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
    def failed(self):
        return self.status == FAILED

    @property
    def done(self):
        """Returns True if the step is finished (either COMPLETE or SKIPPED)"""
        return self.completed or self.skipped or self.failed

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

    def fail(self):
        """A shortcut for set_status(FAILED)"""
        self.set_status(FAILED)


class Plan(OrderedDict):
    """A collection of :class:`Step` objects to execute.

    The :class:`Plan` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. It will run the
    steps in the order they are added to the `Plan` via the :func:`Plan.add`
    function. If a `Step` specifies requirements, the `Plan` will wait until
    the required stacks have completed before executing that `Step`.

    Args:
        description (str): description of the plan
        sleep_time (int, optional): the amount of time that will be passed to
            the `wait_func`. Default: 5 seconds.
        wait_func (func, optional): the function to be called after each pass
            of running stacks. This defaults to :func:`time.sleep` and will
            sleep for the given `sleep_time` before starting the next pass.
            Default: :func:`time.sleep`

    """

    def __init__(self, description, sleep_time=5, wait_func=None,
                 watch_func=None, logger_type=None, *args, **kwargs):
        self.description = description
        self.sleep_time = sleep_time
        self.logger_type = logger_type
        if wait_func is not None:
            if not callable(wait_func):
                raise ImproperlyConfigured(self.__class__,
                                           "\"wait_func\" must be a callable")
            self._wait_func = wait_func
        else:
            self._wait_func = time.sleep

        self._watchers = {}
        self._watch_func = watch_func
        self.id = uuid.uuid4()
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
            requires=requires,
        )

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

    def list_failed(self):
        """A shortcut for list_status(SKIPPED)"""
        return self.list_status(FAILED)

    def list_pending(self):
        """Pending is any task that isn't COMPLETE or SKIPPED or FAILED. """
        return [step for step in self.iteritems() if not step[1].done]

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
            failed = False
            for required_stack in step.requires:
                if self[required_stack].failed:
                    logger.warn(
                        'Stack \"%s\" cannot be updated, as dependency \"%s\" '
                        'has failed',
                        step_name, required_stack)
                    step.set_status(FailedStatus("dependency has failed"))
                    failed = True
                    break

                if not self[required_stack].completed and \
                        not self[required_stack].skipped:
                    waiting_on.append(required_stack)

            if failed:
                continue

            if waiting_on:
                logger.debug(
                    "Stack: \"%s\" waiting on required stacks: %s",
                    step.stack.name,
                    ", ".join(waiting_on),
                )
                continue

            # Kick off watchers - used for tailing the stack
            if (
                not step.done and
                self._watch_func and
                step_name not in self._watchers
            ):
                process = multiprocessing.Process(
                    target=self._watch_func,
                    args=(step.stack,)
                )
                self._watchers[step_name] = process
                process.start()

            try:
                status = step.run()
            except CancelExecution:
                status = SkippedStatus(reason="canceled execution")

            if not isinstance(status, Status):
                raise ValueError(
                    "Step run_func must return a valid Status object. "
                    "(Returned type: %s)" % (type(status)))
            step.set_status(status)

            # Terminate any watchers when step completes
            if step.done and step_name in self._watchers:
                self._terminate_watcher(self._watchers[step_name])

        return self.completed

    def _terminate_watcher(self, watcher):
        if watcher.is_alive():
            watcher.terminate()
            watcher.join()

    def execute(self):
        """Execute the plan.

        This will run through all of the steps registered with the plan and
        submit them in parallel based on their dependencies.
        """

        attempts = 0
        last_md5 = self.md5
        try:
            while not self.completed:
                if (
                    not attempts % self.check_point_interval or
                    self.md5 != last_md5
                ):
                    last_md5 = self.md5
                    self._check_point()

                attempts += 1
                if not self._single_run():
                    self._wait_func(self.sleep_time)

        finally:
            for watcher in self._watchers.values():
                self._terminate_watcher(watcher)

        self._check_point()

        failed_stacks = [step[1].stack for step in self.list_failed()]
        if failed_stacks:
            raise PlanFailed(failed_stacks)

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

    def dump(self, directory, context, provider=None):
        steps = 1
        logger.info("Dumping \"%s\"...", self.description)
        directory = os.path.expanduser(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)

        while not self.completed:
            step_name, step = self.list_pending()[0]
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
