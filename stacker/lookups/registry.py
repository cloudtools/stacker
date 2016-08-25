from ..exceptions import UnknownLookupType
from ..util import load_object_from_string

from . import output

LOOKUP_HANDLERS = {}
DEFAULT_LOOKUP = output.TYPE_NAME


def register_lookup_handler(lookup_type, handler_or_path):
    handler = handler_or_path
    if isinstance(handler_or_path, basestring):
        handler = load_object_from_string(handler_or_path)
    LOOKUP_HANDLERS[lookup_type] = handler


def resolve_lookups(lookups, context, provider):
    resolved_lookups = {}
    for lookup in lookups:
        try:
            handler = LOOKUP_HANDLERS[lookup.type]
        except KeyError:
            raise UnknownLookupType(lookup)
        resolved_lookups[lookup] = handler(
            value=lookup.input,
            context=context,
            provider=provider,
        )
    return resolved_lookups

register_lookup_handler(output.TYPE_NAME, output.handler)
