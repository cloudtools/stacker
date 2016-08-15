from logging import StreamHandler
from colorama.ansi import (
    Cursor,
    clear_line,
)


class LogLoopStreamHandler(StreamHandler):
    """Logging handler that supports updating log lines while in a loop.

    This is used within the Stacker Plan to make the output while waiting for
    stacks to complete less verbose. Without this handler, the plan status
    would be logged as N number of lines each time we output the checkpoint.
    With this handler, we'll output the plan status once and keep updating the
    same lines with updated values.

    """

    def __init__(self, *args, **kwargs):
        super(LogLoopStreamHandler, self).__init__(*args, **kwargs)
        self.loops = {}

    def format(self, record):
        msg = super(LogLoopStreamHandler, self).format(record)
        if record.__dict__.get("loop"):
            msg = "{}{}".format(clear_line(), msg)
        return msg

    def emit(self, record):
        stream = self.stream
        loop_id = record.__dict__.get("loop")
        reset = record.__dict__.get("reset")
        last_updated = record.__dict__.get("last_updated")
        if last_updated:
            record.__dict__["created"] = last_updated

        if loop_id:
            first = loop_id not in self.loops
            if first:
                self.loops[loop_id] = 0

            count = self.loops[loop_id]
            if not first and reset:
                self.loops[loop_id] = 0
                stream.write("{}\n".format(Cursor.UP(count + 1)))
                stream.flush()
            self.loops[loop_id] += 1
        return super(LogLoopStreamHandler, self).emit(record)
