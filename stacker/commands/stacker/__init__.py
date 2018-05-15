import logging

from .build import Build
from .destroy import Destroy
from .info import Info
from .diff import Diff
from .graph import Graph
from .base import BaseCommand
from ...config import render_parse_load as load_config
from ...context import Context
from ...providers.aws import default
from ... import __version__
from ... import session_cache

logger = logging.getLogger(__name__)


class Stacker(BaseCommand):

    name = "stacker"
    subcommands = (Build, Destroy, Info, Diff, Graph)

    def configure(self, options, **kwargs):
        super(Stacker, self).configure(options, **kwargs)
        if options.interactive:
            logger.info("Using interactive AWS provider mode.")
        else:
            logger.info("Using default AWS provider mode")

        config = load_config(
            options.config.read(),
            environment=options.environment,
            validate=True)

        session_cache.default_profile = options.profile

        options.provider_builder = default.ProviderBuilder(
            region=options.region,
            interactive=options.interactive,
            replacements_only=options.replacements_only,
            recreate_failed=options.recreate_failed,
            service_role=config.service_role,
        )

        options.context = Context(
            environment=options.environment,
            config=config,
            # Allow subcommands to provide any specific kwargs to the Context
            # that it wants.
            **options.get_context_kwargs(options)
        )

    def add_arguments(self, parser):
        parser.add_argument("--version", action="version",
                            version="%%(prog)s %s" % (__version__,))
