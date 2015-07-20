from collections import OrderedDict
import logging
import time

from collections import namedtuple

logger = logging.getLogger(__name__)

Status = namedtuple('Status', ['name', 'code'])
PENDING = Status('pending', 0)
SUBMITTED = Status('submitted', 1)
COMPLETE = Status('complete', 2)
SKIPPED = Status('skipped', 3)


class Step(object):

    def __init__(self, stack, index, run_func, completion_func=None,
                 skip_func=None):
        self.stack = stack
        self.status = PENDING
        self.index = index
        self._run_func = run_func
        self._completion_func = completion_func
        self._skip_func = skip_func

    def __repr__(self):
        return '<stacker.plan.Step:%s:%s>' % (
            self.index + 1,
            self.stack.name,
        )

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
        return self._run_func(results, self.stack, status=self.status)

    def set_status(self, status):
        logger.debug("Setting %s state to %s.", self.stack.name, status.name)
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
    """Used to organize the execution of cloudformation steps"""

    def __init__(self, details, provider, sleep_time=5, max_attempts=10, *args, **kwargs):
        self.details = details
        self.provider = provider
        self.sleep_time = sleep_time
        self.max_attempts = max_attempts
        super(Plan, self).__init__(*args, **kwargs)

    def add(self, stack, run_func, completion_func=None, skip_func=None):
        self[stack.name] = Step(
            stack=stack,
            index=len(self.keys()),
            run_func=run_func,
            completion_func=completion_func,
            skip_func=skip_func,
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
        """ Pending is any task that isn't COMPLETE or SKIPPED. """
        return [step for step in self.iteritems() if (
            step[1].status != COMPLETE and
            step[1].status != SKIPPED
        )]

    @property
    def completed(self):
        if self.list_pending():
            return False
        return True

    def execute(self):
        results = {}
        attempts = 0
        while not self.completed:
            step_name, step = self.list_pending()[0]
            attempts += 1
            if not attempts % 10:
                self._check_point(step_name)

            status = step.run(results)
            if not isinstance(status, Status):
                raise ValueError('Step run_func must return a valid Status')

            if status is COMPLETE:
                attempts = 0
                results[step_name] = step.complete()
            elif status is SKIPPED:
                results[step_name] = step.skip()
            else:
                step.set_status(status)
                time.sleep(self.sleep_time)

        self._check_point()
        return results

    def outline(self, level=logging.INFO, execute_helper=False):
        steps = 1
        logger.log(level, 'Plan "%s":', self.details)
        while not self.completed:
            step_name, step = self.list_pending()[0]
            logger.log(
                level,
                '  - step: %s: target: "%s", action: "%s"',
                steps,
                step_name,
                step._run_func.__name__,
            )
            # Set the status to COMPLETE directly so we don't call the completion func
            step.status = COMPLETE
            steps += 1

        if execute_helper:
            logger.log(level, 'To execute this plan, run with "-f, --force" flag.')

    def _check_point(self, current_step_name=None):
        if current_step_name:
            logger.info('Waiting on stack: %s', current_step_name)

        logger.info('Plan Status:')
        for step_name, step in self.iteritems():
            logger.info('  - step "%s": %s', step_name, step.status.name)
