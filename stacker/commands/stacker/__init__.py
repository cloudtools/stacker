import copy
import logging

from .build import Build
from .destroy import Destroy
from .info import Info
from .diff import Diff
from .base import BaseCommand
from ...context import Context
from ...providers.aws import (
    default,
    interactive,
)
from ... import __version__

logger = logging.getLogger(__name__)


class Stacker(BaseCommand):

    name = "stacker"
    subcommands = (Build, Destroy, Info, Diff)

    def configure(self, options, **kwargs):
        super(Stacker, self).configure(options, **kwargs)
        if options.interactive:
            logger.info('Using Interactive AWS Provider')
            options.provider = interactive.Provider(
                region=options.region,
                replacements_only=options.replacements_only,
            )
        else:
            logger.info('Using Default AWS Provider')
            options.provider = default.Provider(region=options.region)
        options.context = Context(
            environment=options.environment,
            variables=copy.deepcopy(options.variables),
            logger_type=self.logger_type,
            # Allow subcommands to provide any specific kwargs to the Context
            # that it wants.
            **options.get_context_kwargs(options)
        )
        options.context.load_config(options.config.read())

    def add_arguments(self, parser):
        parser.add_argument("--version", action="version",
                            version="%%(prog)s %s" % (__version__,))
