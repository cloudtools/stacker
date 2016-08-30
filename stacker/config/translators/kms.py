# NOTE: The translator is going to be deprecated in favor of the lookup
from ...lookups.handlers.kms import handler


def kms_simple_constructor(loader, node):
    value = loader.construct_scalar(node)
    return handler(value)
