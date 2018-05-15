import threading
import logging
from getpass import getpass


logger = logging.getLogger(__name__)


def get_raw_input(message):
    """ Just a wrapper for raw_input for testing purposes. """
    return raw_input(message)


class UI(object):
    """ This class is used internally by stacker to perform I/O with the
    terminal in a multithreaded environment. It ensures that two threads don't
    write over each other while asking a user for input (e.g. in interactive
    mode).
    """

    def __init__(self):
        self._lock = threading.RLock()

    def lock(self, *args, **kwargs):
        """Obtains an exclusive lock on the UI for the currently executing
        thread."""
        return self._lock.acquire()

    def unlock(self, *args, **kwargs):
        return self._lock.release()

    def info(self, *args, **kwargs):
        """Logs the line of the current thread owns the underlying lock, or
        blocks."""
        self.lock()
        try:
            return logger.info(*args, **kwargs)
        finally:
            self.unlock()

    def ask(self, message):
        """This wraps the built-in raw_input function to ensure that only 1
        thread is asking for input from the user at a give time. Any process
        that tries to log output to the terminal will block while the user is
        being prompted."""
        self.lock()
        try:
            return get_raw_input(message)
        finally:
            self.unlock()

    def getpass(self, *args):
        """Wraps getpass to lock the UI."""
        try:
            self.lock()
            return getpass(*args)
        finally:
            self.unlock()


# Global UI object for other modules to use.
ui = UI()
