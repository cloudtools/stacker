from collections import namedtuple
import re

from .registry import DEFAULT_LOOKUP
# export resolve_lookups at this level
from .registry import resolve_lookups  # NOQA
from .registry import register_lookup_handler  # NOQA

LOOKUP_REGEX = re.compile("""
\$\{                                   # opening brace for the lookup
((?P<type>[._\-a-zA-Z0-9]*(?=\s))      # type of lookup, must be followed by a
                                       # space to allow for defaulting to
                                       # "output" type
?\s*                                   # any number of spaces separating the
                                       # type from the input
(?P<input>[@\+\/,\._\-a-zA-Z0-9\:\s]+) # the input value to the lookup
)\}                                    # closing brace of the lookup
""", re.VERBOSE)

Lookup = namedtuple("Lookup", ("type", "input", "raw"))


def extract_lookups_from_string(value):
    """Extract any lookups within a string.

    Args:
        value (str): string value we're extracting lookups from

    Returns:
        list: list of :class:`stacker.lookups.Lookup` if any

    """
    lookups = set()
    for match in LOOKUP_REGEX.finditer(value):
        groupdict = match.groupdict()
        raw = match.groups()[0]
        lookup_type = groupdict.get("type") or DEFAULT_LOOKUP
        lookup_input = groupdict.get("input")
        lookups.add(Lookup(lookup_type, lookup_input, raw))
    return lookups


def extract_lookups(value):
    """Recursively extracts any stack lookups within the data structure.

    Args:
        value (one of str, list, dict): a structure that contains lookups to
            output values

    Returns:
        list: list of lookups if any

    """
    lookups = set()
    if isinstance(value, basestring):
        lookups = lookups.union(extract_lookups_from_string(value))
    elif isinstance(value, list):
        for v in value:
            lookups = lookups.union(extract_lookups(v))
    elif isinstance(value, dict):
        for v in value.values():
            lookups = lookups.union(extract_lookups(v))
    return lookups
