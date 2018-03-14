import json
import os
import boto3
import logging
import threading
from .ui import ui


# boto3 client creation is not threadsafe. This lock ensures that only 1 thread
# is building a boto3 client at any given time.
#
# See https://github.com/boto/boto3/issues/801#issuecomment-245455979
# See https://github.com/remind101/stacker/issues/560
_session_lock = threading.RLock()


def get_session(region, profile=None):
    """Creates a boto3 session with a cache. This method is threadsafe even
    though boto3 session creation itself is not.

    Args:
        region (str): The region for the session
        profile (str): The profile for the session

    Returns:
        :class:`boto3.session.Session`: A boto3 session with
            credential caching
    """
    with _session_lock:
        return _get_session(region=region, profile=profile)


def _get_session(region, profile=None):
    session = boto3.Session(region_name=region, profile_name=profile)
    c = session._session.get_component('credential_provider')
    provider = c.get_provider('assume-role')
    provider.cache = CredentialCache()
    provider._prompter = ui.getpass
    return session


logger = logging.getLogger(__name__)


class CredentialCache(object):

    """JSON file cache.
    This provides a dict like interface that stores JSON serializable
    objects.
    The objects are serialized to JSON and stored in a file.  These
    values can be retrieved at a later time.
    """

    CACHE_DIR = os.path.expanduser(
        os.path.join('~', '.aws', 'cli', 'cache'))

    def __init__(self, working_dir=CACHE_DIR):
        self._working_dir = working_dir

    def __contains__(self, cache_key):
        actual_key = self._convert_cache_key(cache_key)
        return os.path.isfile(actual_key)

    def __getitem__(self, cache_key):
        """Retrieve value from a cache key."""
        logger.debug("Getting cached credentials from: %s", self.CACHE_DIR)
        actual_key = self._convert_cache_key(cache_key)
        try:
            with open(actual_key) as f:
                return json.load(f)
        except (OSError, ValueError, IOError):
            raise KeyError(cache_key)

    def __setitem__(self, cache_key, value):
        full_key = self._convert_cache_key(cache_key)
        try:
            file_content = json.dumps(value, default=str)
        except (TypeError, ValueError):
            raise ValueError("Value cannot be cached, must be "
                             "JSON serializable: %s" % value)
        if not os.path.isdir(self._working_dir):
            os.makedirs(self._working_dir)
        with os.fdopen(os.open(full_key,
                               os.O_WRONLY | os.O_CREAT, 0o600), 'w') as f:
            f.truncate()
            f.write(file_content)
            logger.debug(
                "Updating cache with new obtained credentials: %s",
                self.CACHE_DIR)

    def _convert_cache_key(self, cache_key):
        full_path = os.path.join(self._working_dir, cache_key + '.json')
        return full_path
