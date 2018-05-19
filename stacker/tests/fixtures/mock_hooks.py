from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


def mock_hook(provider, context, **kwargs):
    return {"result": kwargs["value"]}
