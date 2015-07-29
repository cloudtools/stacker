import argparse
from collections import Mapping

import yaml

from ..base import BaseCommand


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


def yaml_file_type(yaml_file):
    """ Reads a yaml file and returns the resulting data. """
    with open(yaml_file) as fd:
        return yaml.load(fd)


class StackerCommand(BaseCommand):
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

    def add_arguments(self, parser):
        super(StackerCommand, self).add_arguments(parser)
        parser.add_argument("-p", "--parameter", dest="parameters",
                            metavar="PARAMETER=VALUE", type=key_value_arg,
                            action=KeyValueAction, default={},
                            help="Adds parameters from the command line "
                                 "that can be used inside any of the stacks "
                                 "being built. Can be specified more than once.")
        parser.add_argument('-r', '--region', default='us-east-1',
                            help="The AWS region to launch in. Default: "
                                 "%(default)s")
        parser.add_argument('-v', '--verbose', action='count', default=0,
                            help='Increase output verbosity. May be specified up '
                                 'to twice.')
        parser.add_argument("--stacks", action="append",
                            metavar="STACKNAME", type=str,
                            help="Only work on the stacks given. Can be "
                                 "specified more than once. If not specified "
                                 "then stacker will work on all stacks in the "
                                 "config file.")
        parser.add_argument('environment', type=yaml_file_type,
                            default={},
                            help="Path to a yaml environment file. The values in "
                                 "the environment file can be used in the stack "
                                 "config as if it were a string.Template type: "
                                 "https://docs.python.org/2/library/string.html"
                                 "#template-strings. Must define at least a "
                                 "'namespace'.")
        parser.add_argument('config', type=argparse.FileType(),
                            help="The config file where stack configuration is "
                                 "located. Must be in yaml format.")
