from logging import StreamHandler
from colorama.ansi import (
    Cursor,
    clear_line,
)


class LogLoopStreamHandler(StreamHandler):

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
        index = record.__dict__.get("index")
        if loop_id:
            first = loop_id not in self.loops
            if first:
                self.loops[loop_id] = 0

            count = self.loops[loop_id]
            if not first and index == 0:
                self.loops[loop_id] = 0
                stream.write("{}\n".format(Cursor.UP(count + 1)))
                stream.flush()
            self.loops[loop_id] += 1
        return super(LogLoopStreamHandler, self).emit(record)
