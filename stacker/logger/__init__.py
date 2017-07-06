import sys
import logging

from .handler import LogLoopStreamHandler
from .formatter import ColorFormatter

DEBUG_FORMAT = ("[%(asctime)s] %(levelname)s %(name)s:%(lineno)d"
                "(%(funcName)s): %(message)s")
INFO_FORMAT = ("[%(asctime)s] %(message)s")
COLOR_FORMAT = ("[%(asctime)s] %(color)s%(message)s")

ISO_8601 = "%Y-%m-%dT%H:%M:%S"

BASIC_LOGGER_TYPE = 0
LOOP_LOGGER_TYPE = 1


def setup_logging(verbosity, interactive=False, tail=False):
    enable_loop_logger = (
        verbosity == 0 and
        sys.stdout.isatty() and
        not (interactive or tail)
    )
    log_level = logging.INFO
    log_format = INFO_FORMAT
    if verbosity > 0:
        log_level = logging.DEBUG
        log_format = DEBUG_FORMAT
    if verbosity < 2:
        logging.getLogger("botocore").setLevel(logging.CRITICAL)

    log_type = BASIC_LOGGER_TYPE
    if enable_loop_logger:
        log_type = LOOP_LOGGER_TYPE
        fmt = ColorFormatter(COLOR_FORMAT, ISO_8601)
        hdlr = LogLoopStreamHandler()
        hdlr.setFormatter(fmt)
        logging.root.addHandler(hdlr)
        logging.root.setLevel(log_level)
    else:
        logging.basicConfig(
            format=log_format,
            datefmt=ISO_8601,
            level=log_level,
        )
    return log_type
