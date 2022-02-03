import boto3
import logging
from .ui import ui


logger = logging.getLogger(__name__)


# A global credential cache that can be shared among boto3 sessions. This is
# inherently threadsafe thanks to the GIL:
# https://docs.python.org/3/glossary.html#term-global-interpreter-lock
credential_cache = {}

default_profile = None


def get_session(region, profile=None):
    """Creates a boto3 session with a cache

    Args:
        region (str): The region for the session
        profile (str): The profile for the session

    Returns:
        :class:`boto3.session.Session`: A boto3 session with
            credential caching
    """
    if profile is None:
        logger.debug("No AWS profile explicitly provided. "
                     "Falling back to default.")
        profile = default_profile

    logger.debug("Building session using profile \"%s\" in region \"%s\""
                 % (profile, region))

    session = boto3.Session(region_name=region, profile_name=profile)
    c = session._session.get_component('credential_provider')
    provider = c.get_provider('assume-role')
    provider.cache = credential_cache
    provider._prompter = ui.getpass
    return session
