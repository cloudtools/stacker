from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import operator


class Status(object):
    def __init__(self, name, code, reason=None):
        self.name = name
        self.code = code
        self.reason = reason or getattr(self, "reason", None)

    def _comparison(self, operator, other):
        if hasattr(other, "code"):
            return operator(self.code, other.code)
        return NotImplemented

    def __eq__(self, other):
        return self._comparison(operator.eq, other)

    def __ne__(self, other):
        return self._comparison(operator.ne, other)

    def __lt__(self, other):
        return self._comparison(operator.lt, other)

    def __gt__(self, other):
        return self._comparison(operator.gt, other)

    def __le__(self, other):
        return self._comparison(operator.le, other)

    def __ge__(self, other):
        return self._comparison(operator.ge, other)


class PendingStatus(Status):
    def __init__(self, reason=None):
        super(PendingStatus, self).__init__("pending", 0, reason)


class SubmittedStatus(Status):
    def __init__(self, reason=None):
        super(SubmittedStatus, self).__init__("submitted", 1, reason)


class CompleteStatus(Status):
    def __init__(self, reason=None):
        super(CompleteStatus, self).__init__("complete", 2, reason)


class SkippedStatus(Status):
    def __init__(self, reason=None):
        super(SkippedStatus, self).__init__("skipped", 3, reason)


class FailedStatus(Status):
    def __init__(self, reason=None):
        super(FailedStatus, self).__init__("failed", 4, reason)


class NotSubmittedStatus(SkippedStatus):
    reason = "disabled"


class NotUpdatedStatus(SkippedStatus):
    reason = "locked"


class DidNotChangeStatus(SkippedStatus):
    reason = "nochange"


class StackDoesNotExist(SkippedStatus):
    reason = "does not exist in cloudformation"


PENDING = PendingStatus()
WAITING = PendingStatus(reason="waiting")
SUBMITTED = SubmittedStatus()
COMPLETE = CompleteStatus()
SKIPPED = SkippedStatus()
FAILED = FailedStatus()
INTERRUPTED = FailedStatus(reason="interrupted")
