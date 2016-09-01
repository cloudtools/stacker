"""Handler for fetching outputs from fully qualified stacks.

The `output` handler supports fetching outputs from stacks created within a
sigle config file. Sometimes it's useful to fetch outputs from stacks created
outside of the current config file. `xref` supports this by not using the
:class:`stacker.context.Context` to expand the fqn of the stack.

Example:

    conf_value: ${xref some-fully-qualified-stack-name::SomeOutputName}

"""
from functools import partial

from .output import handler as output_handler

TYPE_NAME = "xref"

# xref is the same as the `output` handler, except the value already contains
# the fully qualified name for the stack we're fetching the output from.
handler = partial(output_handler, fqn=True)
