class Status(object):
    def __init__(self, name, code, reason=None):
        self.name = name
        self.code = code
        self.reason = reason

    def __cmp__(self, other):
        if hasattr(other, "code"):
            return cmp(self.code, other.code)
        return False


class PendingStatus(Status):
    def __init__(self, reason=None):
        super(PendingStatus, self).__init__('pending', 0, reason)


class SubmittedStatus(Status):
    def __init__(self, reason=None):
        super(SubmittedStatus, self).__init__('submitted', 1, reason)


class CompleteStatus(Status):
    def __init__(self, reason=None):
        super(CompleteStatus, self).__init__('complete', 2, reason)


class SkippedStatus(Status):
    reason = None

    def __init__(self, reason=None):
        super(SkippedStatus, self).__init__('skipped', 3,
                                            reason or self.reason)


class NotSubmittedStatus(SkippedStatus):
    reason = "Stack would not be submitted."


class NotUpdatedStatus(SkippedStatus):
    reason = "Stack would not be updated."


class DidNotChangeStatus(SkippedStatus):
    reason = "Stack did not change."


class StackDoesNotExist(SkippedStatus):
    reason = "Stack does not exist."
