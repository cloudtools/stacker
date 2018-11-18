from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from . import LookupHandler


TYPE_NAME = "hook_data"


class HookDataLookup(LookupHandler):
    @classmethod
    def handle(cls, value, context, **kwargs):
        """Returns the value of a key for a given hook in hook_data.

        Format of value:

            <hook_name>::<key>
        """
        try:
            hook_name, key = value.split("::")
        except ValueError:
            raise ValueError("Invalid value for hook_data: %s. Must be in "
                             "<hook_name>::<key> format." % value)

        return context.hook_data[hook_name][key]
