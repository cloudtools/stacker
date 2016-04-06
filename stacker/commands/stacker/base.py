import argparse
from collections import Mapping
import logging

from ...environment import parse_environment

DEBUG_FORMAT = ('[%(asctime)s] %(levelname)s %(name)s:%(lineno)d'
                '(%(funcName)s): %(message)s')
INFO_FORMAT = ('[%(asctime)s] %(message)s')

ISO_8601 = '%Y-%m-%dT%H:%M:%S'


class KeyValueAction(argparse.Action):
    def __init__(self, option_strings, dest, default=None, nargs=None,
                 **kwargs):
        if nargs:
            raise ValueError("nargs not allowed")
        default = default or {}
        super(KeyValueAction, self).__init__(option_strings, dest, nargs,
                                             default=default, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if not isinstance(values, Mapping):
            raise ValueError("type must be 'key_value'")
        if not getattr(namespace, self.dest):
            setattr(namespace, self.dest, {})
        getattr(namespace, self.dest).update(values)


def key_value_arg(string):
    try:
        k, v = string.split("=", 1)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "%s does not match KEY=VALUE format." % string)
    return {k: v}


def environment_file(input_file):
    """Reads a stacker environment file and returns the resulting data."""
    with open(input_file) as fd:
        return parse_environment(fd.read())


class BaseCommand(object):
    """Base class for all stacker subcommands.

    The way argparse handles common arguments that should be passed to the
    subparser is confusing. You can add arguments to the parent parser that
    will get passed to the subparser, but these then need to be provided on the
    command line before specifying the subparser. Furthermore, when viewing the
    help for a subcommand, you can't view these parameters.

    By including shared parameters for stacker commands within this subclass,
    we don't have to redundantly add the parameters we want on all subclasses
    within each subparser and these shared parameters are treated as normal
    arguments to the subcommand.

    """

    name = None
    description = None
    subcommands = tuple()
    subcommands_help = None

    def __init__(self, *args, **kwargs):
        if not self.name:
            raise ValueError('Subcommands must set "name": %s' % (self,))

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
                subparser.set_defaults(
                    get_context_kwargs=subcommand.get_context_kwargs)

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

    def parse_args(self, *vargs):
        parser = argparse.ArgumentParser(description=self.description)
        self.add_subcommands(parser)
        self.add_arguments(parser)
        args = parser.parse_args(*vargs)
        args.environment.update(args.cli_envs)
        return args

    def run(self, options, **kwargs):
        self.setup_logging(options.verbose)

    def configure(self, options, **kwargs):
        pass

    def get_context_kwargs(self, options, **kwargs):
        """Return a dictionary of kwargs that will be used with the Context.

        This allows commands to pass in any specific arguments they define to
        the context.

        Args:
            options (:class:`argparse.Namespace`): arguments that have been
                passed via the command line

        Returns:
            dict: Dictionary that will be passed to Context initializer as
                kwargs.

        """
        return {}

    def add_arguments(self, parser):
        # global arguments that should be available on all stacker subcommands
        parser.add_argument("-p", "--parameter", dest="parameters",
                            metavar="PARAMETER=VALUE", type=key_value_arg,
                            action=KeyValueAction, default={},
                            help="Adds parameters from the command line "
                                 "that can be used inside any of the stacks "
                                 "being built. Can be specified more than "
                                 "once.")
        parser.add_argument("-e", "--env", dest="cli_envs",
                            metavar="ENV=VALUE", type=key_value_arg,
                            action=KeyValueAction, default={},
                            help="Adds environment key/value pairs from "
                                 "the command line. Overrides your "
                                 "environment file settings. Can be specified "
                                 "more than once.")
        parser.add_argument("-r", "--region", default="us-east-1",
                            help="The AWS region to launch in. Default: "
                                 "%(default)s")
        parser.add_argument("-v", "--verbose", action="count", default=0,
                            help="Increase output verbosity. May be specified "
                                 "up to twice.")
        parser.add_argument('environment', type=environment_file,
                            default={},
                            help="Path to a simple `key: value` pair environment "
                                 "file. The values in the environment file can "
                                 "be used in the stack config as if it were a "
                                 "string.Template type: "
                                 "https://docs.python.org/2/library/string.html"
                                 "#template-strings. Must define at least a "
                                 "'namespace'.")
        parser.add_argument('config', type=argparse.FileType(),
                            help="The config file where stack configuration is "
                                 "located. Must be in yaml format.")
