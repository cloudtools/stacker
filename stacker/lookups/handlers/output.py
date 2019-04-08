from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re
from collections import namedtuple

import yaml

from stacker.exceptions import StackDoesNotExist
from . import LookupHandler

TYPE_NAME = "output"

Output = namedtuple("Output", ("stack_name", "output_name"))


class OutputLookup(LookupHandler):
    @classmethod
    def handle(cls, value, context, provider):
        """Fetch an output from the designated stack."""

        d = deconstruct(value)
        try:
            stack = context.get_stack(d.stack_name)
            if not stack:
                raise StackDoesNotExist(d.stack_name)
            outputs = provider.get_outputs(stack.fqn)
        except StackDoesNotExist:
            raise LookupError("Stack is missing from configuration or not "
                              "deployed: {}".format(d.stack_name))

        try:
            return outputs[d.output_name]
        except KeyError:
            available_lookups = yaml.safe_dump(
                list(outputs.keys()), default_flow_style=False)
            msg = ("Lookup missing from stack: {}::{}. "
                   "Available lookups:\n{}")
            raise LookupError(msg.format(
                d.stack_name, d.output_name, available_lookups))

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
