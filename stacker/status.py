class Status(object):
    def __init__(self, name, code, reason=None):
        self.name = name
        self.code = code
        self.reason = reason or getattr(self, "reason", None)

    def cmp(self, a, b):
        try:
            return cmp(a, b)
        except NameError:
            # Python3 doesn't have cmp function.
            return ((a > b) - (a < b))

    def __cmp__(self, other):
        if hasattr(other, "code"):
            return self.cmp(self.code, other.code)
        raise Exception("Both Status objects must have a `code` attribute.")


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
SUBMITTED = SubmittedStatus()
COMPLETE = CompleteStatus()
SKIPPED = SkippedStatus()
FAILED = FailedStatus()
INTERRUPTED = FailedStatus(reason="interrupted")
