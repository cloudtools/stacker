"""Handler for fetching outputs from fully qualified stacks.

The `output` handler supports fetching outputs from stacks created within a
sigle config file. Sometimes it's useful to fetch outputs from stacks created
outside of the current config file. `rxref` supports this by not using the
:class:`stacker.context.Context` to expand the fqn of the stack.

Example:

    conf_value: ${rxref
        some-relative-fully-qualified-stack-name::SomeOutputName}

"""
from functools import partial

from .output import handler as output_handler

TYPE_NAME = "rxref"

# rxref is the same as the `output` handler, except the value already contains
# the relative fully qualified name for the stack we're fetching the output
# from.
handler = partial(output_handler, rfqn=True)
