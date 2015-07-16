# TODO add a better description about all the actions
"""Description about what stacker does
"""
import copy

from .build import Build
from .destroy import Destroy
from ..base import BaseCommand
from ...context import Context
from ...providers import aws


class Stacker(BaseCommand):

    name = 'stacker'
    description = __doc__
    subcommands = (Build, Destroy)

    def configure(self, options, **kwargs):
        super(Stacker, self).configure(options, **kwargs)
        options.provider = aws.Provider(region=options.region)
        options.context = Context(
            namespace=options.namespace,
            environment=options.environment,
            parameters=copy.deepcopy(options.parameters),
            stack_names=options.stacks,
        )
        options.context.load_config(options.config.read())
