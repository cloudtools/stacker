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
        completion_func (Optional[func]): Optional function that should be run
            when the step is complete. This should be used to return some
            result of the step.
        skip_func (Optional[func]): Optional function that should be run when
            the step is skipped. This can be used to return results from the
            step, without risking calling a completion function agian.
        requires (Optional[list]): List of stacks this step depends on being
            completed before running. This step will not be executed unless the
            required stacks have either completed or skipped.

    """

    def __init__(self, stack, run_func, completion_func=None,
                 skip_func=None, requires=None, **kwargs):
        self.stack = stack
        self.status = PENDING
        self.requires = requires or []
        self.kwargs = kwargs
        self._run_func = run_func
        self._completion_func = completion_func
        self._skip_func = skip_func

    def __repr__(self):
        return '<stacker.plan.Step:%s>' % (self.stack.fqn,)

    @property
    def completed(self):
        return self.status == COMPLETE

    @property
    def skipped(self):
        return self.status == SKIPPED

    @property
    def submitted(self):
        return self.status.code >= SUBMITTED.code

    def submit(self):
        self.set_status(SUBMITTED)

    def run(self, results):
        return self._run_func(results, self.stack, status=self.status,
                              **self.kwargs)

    def set_status(self, status):
        if status is not self.status:
            logger.debug("Setting %s state to %s.", self.stack.name,
                         status.name)
            self.status = status

    def complete(self):
        self.set_status(COMPLETE)
        if self._completion_func and callable(self._completion_func):
            return self._completion_func(self.stack)

    def skip(self):
        self.set_status(SKIPPED)
        if self._skip_func and callable(self._skip_func):
            return self._skip_func(self.stack)


class Plan(OrderedDict):
    """A collection of `Step`s to execute.

    The `Plan` helps organize the steps needed to execute a particular action
    for a set of `Stack`s. It will run the steps in the order they are added to
    the `Plan` via the `add` function. If a `Step` specifies requirements, the
    `Plan` will wait until the required stacks have completed before executing
    that `Step`.

    Args:
        description (str): description of the plan
        sleep_time (Optional[int]): the amount of time that will be passed to
            the `wait_func`
        wait_func (Optional[func]): the function to be called after each pass
            of running stacks. This defaults to `time.sleep` and will sleep for
            the given `sleep_time` before starting the next pass.

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

    def add(self, stack, run_func, completion_func=None, skip_func=None,
            requires=None, **kwargs):
        """Add a new step to the plan."""
        self[stack.fqn] = Step(
            stack=stack,
            run_func=run_func,
            completion_func=completion_func,
            skip_func=skip_func,
            requires=requires,
            **kwargs
        )

    def list_status(self, status):
        return [step for step in self.iteritems() if step[1].status == status]

    def list_completed(self):
        return self.list_status(COMPLETE)

    def list_submitted(self):
        return self.list_status(SUBMITTED)

    def list_skipped(self):
        return self.list_status(SKIPPED)

    def list_pending(self):
        """Pending is any task that isn't COMPLETE or SKIPPED. """
        return [step for step in self.iteritems() if (
            step[1].status != COMPLETE and
            step[1].status != SKIPPED
        )]

    @property
    def completed(self):
        if self.list_pending():
            return False
        return True

    def execute(self, results=None):
        """Execute the plan.

        This will run through all of the steps registered with the plan and
        submit them in parallel based on their dependencies. The results will
        be returned once all steps have either been skipped or completed.

        Args:
            results (Optional[dict]): The dictionary that should be used to
                store the results

        """

        if results is None:
            results = {}

        attempts = 0
        while not self.completed:
            attempts += 1
            if not attempts % 10:
                self._check_point()

            for step_name, step in self.list_pending():
                waiting_on = []
                for required_stack in step.requires:
                    if required_stack not in results:
                        waiting_on.append(required_stack)

                if waiting_on:
                    logger.debug(
                        'Stack: "%s" waiting on required stacks: %s',
                        step.stack.name,
                        ', '.join(waiting_on),
                    )
                    continue

                status = step.run(results)
                if not isinstance(status, Status):
                    raise ValueError('Step run_func must return a valid '
                                     'Status')

                if status is COMPLETE:
                    results[step_name] = step.complete()
                elif status is SKIPPED:
                    results[step_name] = step.skip()
                else:
                    step.set_status(status)

            if not self.completed:
                self._wait_func(self.sleep_time)

        self._check_point()
        return results

    def outline(self, level=logging.INFO, execute_helper=False):
        """Print an outline of the actions the plan is going to take.

        The outline will represent the rough ordering of the steps that will be
        taken.

        Args:
            level (Optional[int]): a valid log level that should be used to log
                the outline
            execute_helper (Optional[bool]): boolean for whether or not a line
                instructing the user to pass the "force" flag should be
                provided.

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

        if execute_helper:
            logger.log(level, 'To execute this plan, run with "-f, --force" '
                              'flag.')

    def _check_point(self):
        logger.info('Plan Status:')
        for step_name, step in self.iteritems():
            logger.info('  - step "%s": %s', step_name, step.status.name)
