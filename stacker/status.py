class Status(object):
    def __init__(self, name, code, reason=None):
        self.name = name
        self.code = code
        self.reason = reason or getattr(self, "reason", None)

    def __cmp__(self, other):
        if hasattr(other, "code"):
            return cmp(self.code, other.code)
        return False


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
