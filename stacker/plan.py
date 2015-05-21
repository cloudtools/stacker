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

    def __init__(self, stack, index, run_func, completion_func=None):
        self.stack = stack
        self.status = PENDING
        self.index = index
        self._run_func = run_func
        self._completion_func = completion_func

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
        self.submit()
        return self._run_func(results, self.stack)

    def set_status(self, status):
        logger.debug("Setting %s state to %s.", self.name, status.name)
        self.status = status

    def complete(self):
        self.set_status(COMPLETE)
        if self._completion_func and callable(self._completion_func):
            return self._completion_func(self.stack)

    def skip(self):
        self.set_status(SKIPPED)


class Plan(OrderedDict):
    """ Used to organize the order in which stacks will be created/updated.
    """

    def __init__(self, provider, sleep_time=5, max_attempts=10, *args, **kwargs):
        self.provider = provider
        self.sleep_time = sleep_time
        self.max_attempts = max_attempts
        super(Plan, self).__init__(*args, **kwargs)

    def add(self, stack, run_func, completion_func=None):
        self[stack.name] = Step(
            stack=stack,
            index=len(self.keys()),
            run_func=run_func,
            completion_func=completion_func,
        )

    def list_status(self, status):
        result = OrderedDict()
        for k, record in self.items():
            if record.status == status:
                result[k] = record
        return result

    def list_completed(self):
        return self.list_status(COMPLETE)

    def list_submitted(self):
        return self.list_status(SUBMITTED)

    def list_skipped(self):
        return self.list_status(SKIPPED)

    def list_pending(self):
        """ Pending is any task that isn't COMPLETE or SKIPPED. """
        result = OrderedDict()
        for k, record in self.items():
            if record.status != COMPLETE and record.status != SKIPPED:
                result[k] = record
        return result

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
                logger.info("Waiting on stack: %s", step_name)

            state = step.run(results)
            if state.code == COMPLETE.code:
                attempts = 0
                results[step_name] = step.complete()
            elif state.code == SKIPPED.code:
                step.skip()
            else:
                time.sleep(self.sleep_time)
        return results
