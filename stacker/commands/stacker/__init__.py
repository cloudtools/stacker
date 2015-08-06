import copy

from .build import Build
from .destroy import Destroy
from .info import Info
from ..base import BaseCommand
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
            stack_names=options.stacks,
        )
        options.context.load_config(options.config.read())
