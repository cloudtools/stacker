import copy

from .build import Build
from .destroy import Destroy
from .info import Info
from .base import BaseCommand
from ...context import Context
from ...providers import aws


class Stacker(BaseCommand):

    name = 'stacker'
    subcommands = (Build, Destroy, Info)

    def configure(self, options, **kwargs):
        super(Stacker, self).configure(options, **kwargs)
        options.provider = aws.Provider(region=options.region)
        options.context = Context(
            environment=options.environment,
            parameters=copy.deepcopy(options.parameters),
            # We use
            # set_default(get_context_kwargs=subcommand.get_context_kwargs) so
            # the subcommand can provide any specific kwargs to the Context
            # that it wants. We need to pass down the options so it can
            # reference any arguments it defined.
            **options.get_context_kwargs(options)
        )
        options.context.load_config(options.config.read())
