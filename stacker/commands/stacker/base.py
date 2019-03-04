from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import argparse
import threading
import signal
from collections import Mapping
import logging

from ...environment import parse_environment

logger = logging.getLogger(__name__)

SIGNAL_NAMES = {
    signal.SIGINT: "SIGINT",
    signal.SIGTERM: "SIGTERM",
}


def cancel():
    """Returns a threading.Event() that will get set when SIGTERM, or
    SIGINT are triggered. This can be used to cancel execution of threads.
    """
    cancel = threading.Event()

    def cancel_execution(signum, frame):
        signame = SIGNAL_NAMES.get(signum, signum)
        logger.info("Signal %s received, quitting "
                    "(this can take some time)...", signame)
        cancel.set()

    signal.signal(signal.SIGINT, cancel_execution)
    signal.signal(signal.SIGTERM, cancel_execution)
    return cancel


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
            raise ValueError("type must be \"key_value\"")
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

    def __init__(self, setup_logging=None, *args, **kwargs):
        self.setup_logging = setup_logging
        if not self.name:
            raise ValueError("Subcommands must set \"name\": %s" % (self,))

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

    def parse_args(self, *vargs):
        parser = argparse.ArgumentParser(description=self.description)
        self.add_subcommands(parser)
        self.add_arguments(parser)
        args = parser.parse_args(*vargs)
        args.environment.update(args.cli_envs)
        return args

    def run(self, options, **kwargs):
        pass

    def configure(self, options, **kwargs):
        if self.setup_logging:
            self.setup_logging(options.verbose, self.config.log_formats)

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
        parser.add_argument(
            "-e", "--env", dest="cli_envs", metavar="ENV=VALUE",
            type=key_value_arg, action=KeyValueAction, default={},
            help="Adds environment key/value pairs from the command line. "
                 "Overrides your environment file settings. Can be specified "
                 "more than once.")
        parser.add_argument(
            "-r", "--region",
            help="The default AWS region to use for all AWS API calls.")
        parser.add_argument(
            "-p", "--profile",
            help="The default AWS profile to use for all AWS API calls. If "
                 "not specified, the default will be according to http://bo"
                 "to3.readthedocs.io/en/latest/guide/configuration.html.")
        parser.add_argument(
            "-v", "--verbose", action="count", default=0,
            help="Increase output verbosity. May be specified up to twice.")
        parser.add_argument(
            "environment", type=environment_file, nargs='?', default={},
            help="Path to a simple `key: value` pair environment file. The "
                 "values in the environment file can be used in the stack "
                 "config as if it were a string.Template type: "
                 "https://docs.python.org/2/library/"
                 "string.html#template-strings.")
        parser.add_argument(
            "config", type=argparse.FileType(),
            help="The config file where stack configuration is located. Must "
                 "be in yaml format. If `-` is provided, then the config will "
                 "be read from stdin.")
        parser.add_argument(
            "-i", "--interactive", action="store_true",
            help="Enable interactive mode. If specified, this will use the "
                 "AWS interactive provider, which leverages Cloudformation "
                 "Change Sets to display changes before running "
                 "cloudformation templates. You'll be asked if you want to "
                 "execute each change set. If you only want to authorize "
                 "replacements, run with \"--replacements-only\" as well.")
        parser.add_argument(
            "--replacements-only", action="store_true",
            help="If interactive mode is enabled, stacker will only prompt to "
                 "authorize replacements.")
        parser.add_argument(
            "--recreate-failed", action="store_true",
            help="Destroy and re-create stacks that are stuck in a failed "
                 "state from an initial deployment when updating.")
