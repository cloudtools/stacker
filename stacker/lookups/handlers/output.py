from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re
from collections import namedtuple

from . import LookupHandler

TYPE_NAME = "output"

Output = namedtuple("Output", ("stack_name", "output_name"))


class OutputLookup(LookupHandler):
    @classmethod
    def handle(cls, value, context=None, **kwargs):
        """Fetch an output from the designated stack.

        Args:
            value (str): string with the following format:
                <stack_name>::<output_name>, ie. some-stack::SomeOutput
            context (:class:`stacker.context.Context`): stacker context

        Returns:
            str: output from the specified stack

        """

        if context is None:
            raise ValueError('Context is required')

        d = deconstruct(value)
        stack = context.get_stack(d.stack_name)
        return stack.outputs[d.output_name]

    @classmethod
    def dependencies(cls, lookup_data):
        # try to get the stack name
        stack_name = ''
        for data_item in lookup_data:
            if not data_item.resolved():
                # We encountered an unresolved substitution.
                # StackName is calculated dynamically based on context:
                #  e.g. ${output ${default var::source}::name}
                # Stop here
                return set()
            stack_name = stack_name + data_item.value()
            match = re.search(r'::', stack_name)
            if match:
                stack_name = stack_name[0:match.start()]
                return {stack_name}
            # else: try to append the next item

        # We added all lookup_data, and still couldn't find a `::`...
        # Probably an error...
        return set()


def deconstruct(value):

    try:
        stack_name, output_name = value.split("::")
    except ValueError:
        raise ValueError("output handler requires syntax "
                         "of <stack>::<output>.  Got: %s" % value)

    return Output(stack_name, output_name)
