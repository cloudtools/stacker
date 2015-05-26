import argparse
import logging

DEBUG_FORMAT = ('[%(asctime)s] %(levelname)s %(name)s:%(lineno)d'
                '(%(funcName)s) - %(message)s')
INFO_FORMAT = ('[%(asctime)s] %(message)s')

ISO_8601 = '%Y-%m-%dT%H:%M:%S'


class BaseCommand(object):

    name = None
    description = None
    subcommands = tuple()
    subcommands_help = None

    def __init__(self, *args, **kwargs):
        if not self.name:
            raise ValueError('Subcommands must set "name": %s' % (self,))

    def add_arguments(self, parser):
        if not self.subcommands:
            parser.set_defaults(run=self.run)

    def add_subcommands(self, parser):
        if self.subcommands:
            subparsers = parser.add_subparsers(help=self.subcommands_help)
            for subcommand_class in self.subcommands:
                subcommand = subcommand_class()
                subparser = subparsers.add_parser(
                    subcommand.name,
                    description=subcommand.description,
                )
                subcommand.add_arguments(subparser)
                subparser.set_defaults(run=subcommand.run)

    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.name)
        return self._logger

    def setup_logging(self, verbosity):
        log_level = logging.INFO
        log_format = INFO_FORMAT
        if verbosity > 0:
            log_level = logging.DEBUG
            log_format = DEBUG_FORMAT
        if verbosity < 2:
            logging.getLogger('boto').setLevel(logging.CRITICAL)

        return logging.basicConfig(
            format=log_format,
            datefmt=ISO_8601,
            level=log_level,
        )

    def parse_args(self):
        parser = argparse.ArgumentParser(description=self.description)
        self.add_arguments(parser)
        self.add_subcommands(parser)
        return parser.parse_args()

    def run(self, options, **kwargs):
        self.setup_logging(options.verbose)

    def configure(self, options, **kwargs):
        pass
