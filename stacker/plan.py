from collections import OrderedDict
import logging
import time

from collections import namedtuple

from .exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

Status = namedtuple('Status', ['name', 'code'])
PENDING = Status('pending', 0)
SUBMITTED = Status('submitted', 1)
COMPLETE = Status('complete', 2)
SKIPPED = Status('skipped', 3)


class Step(object):
    """State machine for executing generic actions related to stacks.

    Args:
        stack (`stacker.stack.Stack`): the `Stack` object associated with this
            step
        run_func (func): the function to be run for the given stack
        requires (Optional[list]): List of stacks this step depends on being
            completed before running. This step will not be executed unless the
            required stacks have either completed or skipped.

    """

    def __init__(self, stack, run_func, requires=None):
        self.stack = stack
        self.status = PENDING
        self.requires = requires or []
        self._run_func = run_func

    def __repr__(self):
        return '<stacker.plan.Step:%s>' % (self.stack.fqn,)

    @property
    def completed(self):
        """Returns True if the step is in a COMPLETE state."""
        return self.status == COMPLETE

    @property
    def skipped(self):
        """Returns True if the step is in a SKIPPED state."""
        return self.status == SKIPPED

    @property
    def submitted(self):
        """Returns True if the step is SUBMITTED, COMPLETE, or SKIPPED."""
        return self.status.code >= SUBMITTED.code

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
        sleep_time (Optional[int]): the amount of time that will be passed to
            the `wait_func`. Default: 5 seconds.
        wait_func (Optional[func]): the function to be called after each pass
            of running stacks. This defaults to :func:`time.sleep` and will
            sleep for the given `sleep_time` before starting the next pass.
            Default: :func:`time.sleep`

    """

    def __init__(self, description, sleep_time=5, wait_func=None, *args,
                 **kwargs):
        self.description = description
        self.sleep_time = sleep_time
        if wait_func is not None:
            if not callable(wait_func):
                raise ImproperlyConfigured(self.__class__,
                                           '"wait_func" must be a callable')
            self._wait_func = wait_func
        else:
            self._wait_func = time.sleep
        super(Plan, self).__init__(*args, **kwargs)

    def add(self, stack, run_func, requires=None):
        """Add a new step to the plan.

        Args:
            stack (:class:`stacker.stack.Stack`): The stack to add to the plan.
            run_func (function): The function to call when the step is ran.
            requires (Optional(list)): A list of other stacks that are required
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

    def list_pending(self):
        """Pending is any task that isn't COMPLETE or SKIPPED. """
        return [step for step in self.iteritems() if (
            step[1].status != COMPLETE and
            step[1].status != SKIPPED
        )]

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
                    'Stack: "%s" waiting on required stacks: %s',
                    step.stack.name,
                    ', '.join(waiting_on),
                )
                continue

            status = step.run()
            if not isinstance(status, Status):
                raise ValueError('Step run_func must return a valid '
                                 'Status')

            step.set_status(status)
        return self.completed

    def execute(self):
        """Execute the plan.

        This will run through all of the steps registered with the plan and
        submit them in parallel based on their dependencies.
        """

        attempts = 0
        while not self.completed:
            attempts += 1
            if not attempts % 10:
                self._check_point()

            if not self._single_run():
                self._wait_func(self.sleep_time)

        self._check_point()

    def outline(self, level=logging.INFO, message=''):
        """Print an outline of the actions the plan is going to take.

        The outline will represent the rough ordering of the steps that will be
        taken.

        Args:
            level (Optional[int]): a valid log level that should be used to log
                the outline
            message (Optional[str]): a message that will be logged to
                the user after the outline has been logged.
        """
        steps = 1
        logger.log(level, 'Plan "%s":', self.description)
        while not self.completed:
            step_name, step = self.list_pending()[0]
            logger.log(
                level,
                '  - step: %s: target: "%s", action: "%s"',
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

    def _check_point(self):
        """Outputs the current status of all steps in the plan."""
        logger.info('Plan Status:')
        for step_name, step in self.iteritems():
            logger.info('  - step "%s": %s', step_name, step.status.name)
