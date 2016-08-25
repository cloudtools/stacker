from collections import namedtuple

TYPE_NAME = "output"

Output = namedtuple("Output", ("stack_name", "output_name"))


def handler(value, context, provider, **kwargs):
    d = deconstruct(value)
    stack_fqn = context.get_fqn(d.stack_name)
    output = provider.get_output(stack_fqn, d.output_name)
    return output


def deconstruct(value):
    stack_name, output_name = value.split("::")
    return Output(stack_name, output_name)
