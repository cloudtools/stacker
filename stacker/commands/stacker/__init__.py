# TODO add a better description about all the actions
"""Description about what stacker does
"""
import argparse
from collections import Mapping
import copy

import yaml


from .build import Build
from .destroy import Destroy
from ..base import BaseCommand
from ...context import Context
from ...providers import aws


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


class Stacker(BaseCommand):

    name = 'stacker'
    description = __doc__
    subcommands = (Build, Destroy)

    def add_arguments(self, parser):
        super(Stacker, self).add_arguments(parser)
        parser.add_argument("-p", "--parameter", dest="parameters",
                            metavar="PARAMETER=VALUE", type=key_value_arg,
                            action=KeyValueAction, default={},
                            help="Adds parameters from the command line "
                                 "that can be used inside any of the stacks "
                                 "being built. Can be specified more than once.")
        parser.add_argument('-r', '--region', default='us-east-1',
                            help="The AWS region to launch in. Default: "
                                 "%(default)s")
        parser.add_argument('-e', '--environment', type=yaml_file_type,
                            default={},
                            help="Path to a yaml environment file. The values in "
                                 "the environment file can be used in the stack "
                                 "config as if it were a string.Template type: "
                                 "https://docs.python.org/2/library/string.html"
                                 "#template-strings")
        parser.add_argument('-v', '--verbose', action='count', default=0,
                            help='Increase output verbosity. May be specified up '
                                 'to twice.')
        parser.add_argument("--stacks", action="append",
                            metavar="STACKNAME", type=str,
                            help="Only work on the stacks given. Can be "
                                 "specified more than once. If not specified "
                                 "then stacker will work on all stacks in the "
                                 "config file.")
        parser.add_argument('namespace',
                            help='The namespace for the stack collection. This '
                                 'will be used as the prefix to the '
                                 'cloudformation stacks as well as the s3 bucket '
                                 'where templates are stored.')
        parser.add_argument('config', type=argparse.FileType(),
                            help="The config file where stack configuration is "
                                 "located. Must be in yaml format.")

    def configure(self, options, **kwargs):
        super(Stacker, self).configure(options, **kwargs)
        options.provider = aws.Provider(region=options.region)
        options.context = Context(
            namespace=options.namespace,
            environment=options.environment,
            parameters=copy.deepcopy(options.parameters),
            stacks=options.stacks,
        )
        options.context.load_config(options.config.read())
