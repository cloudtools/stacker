from __future__ import absolute_import
from __future__ import print_function
from __future__ import division


class LookupHandler(object):
    @classmethod
    def handle(cls, value, context, provider):
        """
        Perform the actual lookup

        :param value: Parameter(s) given to this lookup
        :type value: str
        :param context:
        :param provider:
        :return: Looked-up value
        :rtype: str
        """
        raise NotImplementedError()

    @classmethod
    def dependencies(cls, lookup_data):
        """
        Calculate any dependencies required to perform this lookup.

        Note that lookup_data may not be (completely) resolved at this time.

        :param lookup_data: Parameter(s) given to this lookup
        :type lookup_data VariableValue
        :return: Set of stack names (str) this lookup depends on
        :rtype: set
        """
        del lookup_data  # unused in this implementation
        return set()
