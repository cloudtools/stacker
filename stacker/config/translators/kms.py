from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# NOTE: The translator is going to be deprecated in favor of the lookup
from ...lookups.handlers.kms import KmsLookup


def kms_simple_constructor(loader, node):
    value = loader.construct_scalar(node)
    return KmsLookup.handler(value)
