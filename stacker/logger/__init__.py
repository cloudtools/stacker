from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import sys
import logging

DEBUG_FORMAT = ("[%(asctime)s] %(levelname)s %(threadName)s "
                "%(name)s:%(lineno)d(%(funcName)s): %(message)s")
INFO_FORMAT = ("[%(asctime)s] %(message)s")
COLOR_FORMAT = ("[%(asctime)s] \033[%(color)sm%(message)s\033[39m")

ISO_8601 = "%Y-%m-%dT%H:%M:%S"


class ColorFormatter(logging.Formatter):
    """ Handles colorizing formatted log messages if color provided. """
    def format(self, record):
        if 'color' not in record.__dict__:
            record.__dict__['color'] = 37
        msg = super(ColorFormatter, self).format(record)
        return msg


def setup_logging(verbosity):
    log_level = logging.INFO
    log_format = INFO_FORMAT
    if sys.stdout.isatty():
        log_format = COLOR_FORMAT

    if verbosity > 0:
        log_level = logging.DEBUG
        log_format = DEBUG_FORMAT
    if verbosity < 2:
        logging.getLogger("botocore").setLevel(logging.CRITICAL)

    hdlr = logging.StreamHandler()
    hdlr.setFormatter(ColorFormatter(log_format, ISO_8601))
    logging.root.addHandler(hdlr)
    logging.root.setLevel(log_level)
