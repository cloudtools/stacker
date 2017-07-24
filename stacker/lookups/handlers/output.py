from collections import namedtuple

TYPE_NAME = "output"

Output = namedtuple("Output", ("stack_name", "output_name"))


def handler(value, provider=None, context=None, fqn=False, rfqn=False,
            **kwargs):
    """Fetch an output from the designated stack.

    Args:
        value (str): string with the following format:
            <stack_name>::<output_name>, ie. some-stack::SomeOutput
        provider (:class:`stacker.provider.base.BaseProvider`): subclass of the
            base provider
        context (:class:`stacker.context.Context`): stacker context
        fqn (bool): boolean for whether or not the
            :class:`stacker.context.Context` should resolve the `fqn` of the
            stack.
        rfqn (bool): boolean for whether or not the
            :class:`stacker.context.Context` should resolve the `fqn` of the
            stack prefixed by the namespace variable

    Returns:
        str: output from the specified stack

    """

    if rfqn:
            value = "%s%s%s" % (
                    context.namespace,
                    context.namespace_delimiter,
                    value
            )

    if provider is None:
        raise ValueError('Provider is required')
    if context is None:
        raise ValueError('Context is required')

    d = deconstruct(value)

    stack_fqn = d.stack_name
    if not fqn:
        stack_fqn = context.get_fqn(d.stack_name)

    output = provider.get_output(stack_fqn, d.output_name)
    return output


def deconstruct(value):

    try:
        stack_name, output_name = value.split("::")
    except ValueError:
        raise ValueError("output handler requires syntax "
                         "of <stack>::<output>.  Got: %s" % value)

    return Output(stack_name, output_name)
