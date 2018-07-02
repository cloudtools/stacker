from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from past.builtins import basestring

from ..exceptions import UnknownLookupType, FailedVariableLookup
from ..util import load_object_from_string

from .handlers import output
from .handlers import kms
from .handlers import xref
from .handlers import ssmstore
from .handlers import dynamodb
from .handlers import envvar
from .handlers import rxref
from .handlers import ami
from .handlers import file as file_handler
from .handlers import split
from .handlers import default
from .handlers import hook_data

LOOKUP_HANDLERS = {}


def register_lookup_handler(lookup_type, handler_or_path):
    """Register a lookup handler.

    Args:
        lookup_type (str): Name to register the handler under
        handler_or_path (OneOf[func, str]): a function or a path to a handler

    """
    handler = handler_or_path
    if isinstance(handler_or_path, basestring):
        handler = load_object_from_string(handler_or_path)
    LOOKUP_HANDLERS[lookup_type] = handler


def unregister_lookup_handler(lookup_type):
    """Unregister the specified lookup type.

    This is useful when testing various lookup types if you want to unregister
    the lookup type after the test runs.

    Args:
        lookup_type (str): Name of the lookup type to unregister

    """
    LOOKUP_HANDLERS.pop(lookup_type, None)


def resolve_lookups(variable, context, provider):
    """Resolve a set of lookups.

    Args:
        variable (:class:`stacker.variables.Variable`): The variable resolving
            it's lookups.
        context (:class:`stacker.context.Context`): stacker context
        provider (:class:`stacker.provider.base.BaseProvider`): subclass of the
            base provider

    Returns:
        dict: dict of Lookup -> resolved value

    """
    resolved_lookups = {}
    for lookup in variable.lookups:
        try:
            handler = LOOKUP_HANDLERS[lookup.type]
        except KeyError:
            raise UnknownLookupType(lookup)
        try:
            resolved_lookups[lookup] = handler(
                value=lookup.input,
                context=context,
                provider=provider,
            )
        except Exception as e:
            raise FailedVariableLookup(variable.name, lookup, e)
    return resolved_lookups


register_lookup_handler(output.TYPE_NAME, output.handler)
register_lookup_handler(kms.TYPE_NAME, kms.handler)
register_lookup_handler(ssmstore.TYPE_NAME, ssmstore.handler)
register_lookup_handler(envvar.TYPE_NAME, envvar.handler)
register_lookup_handler(xref.TYPE_NAME, xref.handler)
register_lookup_handler(rxref.TYPE_NAME, rxref.handler)
register_lookup_handler(ami.TYPE_NAME, ami.handler)
register_lookup_handler(file_handler.TYPE_NAME, file_handler.handler)
register_lookup_handler(split.TYPE_NAME, split.handler)
register_lookup_handler(default.TYPE_NAME, default.handler)
register_lookup_handler(hook_data.TYPE_NAME, hook_data.handler)
register_lookup_handler(dynamodb.TYPE_NAME, dynamodb.handler)
