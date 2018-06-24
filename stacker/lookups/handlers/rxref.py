"""Handler for fetching outputs from fully qualified stacks.

The `output` handler supports fetching outputs from stacks created within a
sigle config file. Sometimes it's useful to fetch outputs from stacks created
outside of the current config file. `rxref` supports this by not using the
:class:`stacker.context.Context` to expand the fqn of the stack.

Example:

    conf_value: ${rxref
        some-relative-fully-qualified-stack-name::SomeOutputName}

"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from .output import deconstruct

TYPE_NAME = "rxref"


def handler(value, provider=None, context=None, **kwargs):
    """Fetch an output from the designated stack.

    Args:
        value (str): string with the following format:
            <stack_name>::<output_name>, ie. some-stack::SomeOutput
        provider (:class:`stacker.provider.base.BaseProvider`): subclass of the
            base provider
        context (:class:`stacker.context.Context`): stacker context

    Returns:
        str: output from the specified stack
    """

    if provider is None:
        raise ValueError('Provider is required')
    if context is None:
        raise ValueError('Context is required')

    d = deconstruct(value)
    stack_fqn = context.get_fqn(d.stack_name)
    output = provider.get_output(stack_fqn, d.output_name)
    return output
