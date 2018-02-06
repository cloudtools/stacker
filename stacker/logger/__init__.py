import logging

DEBUG_FORMAT = ("[%(asctime)s] %(levelname)s %(name)s:%(lineno)d"
                "(%(funcName)s): %(message)s")
INFO_FORMAT = ("[%(asctime)s] %(message)s")

ISO_8601 = "%Y-%m-%dT%H:%M:%S"


def setup_logging(verbosity, interactive=False, tail=False):
    log_level = logging.INFO
    log_format = INFO_FORMAT
    if verbosity > 0:
        log_level = logging.DEBUG
        log_format = DEBUG_FORMAT
    if verbosity < 2:
        logging.getLogger("botocore").setLevel(logging.CRITICAL)

    logging.basicConfig(
        format=log_format,
        datefmt=ISO_8601,
        level=log_level,
    )
