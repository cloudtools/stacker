import functools
import logging

import click

from ..environment import parse_environment
from ..logger import setup_logging
from ..providers.aws import (
    default,
    interactive
)
from ..context import Context

logger = logging.getLogger(__name__)


class KeyValueType(click.ParamType):
    name = "key=value"

    def convert(self, value, param, ctx):
        try:
            k, v = value.split("=", 1)
        except ValueError:
            self.fail("%s does not match KEY=VALUE format." % value)
        return (k, v)


KEY_VALUE_TYPE = KeyValueType()


def parse_key_value_arg(ctx, param, value):
    """ Parses KeyValueType parameters into dictionaries. """

    try:
        return dict(value)
    except:
        raise click.BadParameter("argument needs to be in KEY=VALUE format.")


def parse_environment_file(ctx, param, value):
    """ Parses a stacker environment file parameter. """
    return parse_environment(value.read())


def common_parameters(func):
    """ Used to apply common click parameters to commands. """

    @click.option(
        "-e", "--env", multiple=True, metavar="ENV=VALUE",
        type=KEY_VALUE_TYPE, callback=parse_key_value_arg,
        help="Adds environment key/value pairs from the command line. "
             "Overrides your environment file settings. Can be specified "
             "more than once."
    )
    @click.option(
        "-v", "--verbose", count=True,
        help="Increase output verbosity. May be specified "
             "up to twice."
    )
    @click.option(
        "-r", "--region", metavar="AWS_REGION",
        help="The AWS region to launch in."
    )
    @click.option(
        "-i", "--interactive", is_flag=True,
        help="Enable interactive mode. If specified, this will use the AWS "
             "interactive provider, which leverages Cloudformation Change "
             "Sets to display changes before running cloudformation "
             "templates. You'll be asked if you want to execute each change "
             "set. If you only want to authorize replacements, run "
             "with \"--replacements-only\" as well."
    )
    @click.option(
        "--replacements-only", is_flag=True,
        help="If interactive mode is enabled, stacker will only prompt to "
             "authorize replacements."
    )
    @click.argument(
        "environment", type=click.File("rb"), default="dev.env",
        callback=parse_environment_file
    )
    @click.argument(
        "config", type=click.File("rb"), default="stacker.yaml"
    )
    @click.pass_obj
    @functools.wraps(func)
    def wrapper(options, *args, **kwargs):
        # update environment in file with environment from CLI
        environment = kwargs["environment"]
        environment.update(kwargs["env"])

        if kwargs["interactive"]:
            logger.info("Using Interactive AWS Provider")
            provider = interactive.Provider(
                region=kwargs["region"],
                replacements_only=kwargs["replacements_only"],
            )
        else:
            logger.info("Using Default AWS Provider")
            provider = default.Provider(region=kwargs["region"])
        options["provider"] = provider
        options["context"] = Context(
            environment=environment,
            logger_type=setup_logging(
                kwargs["verbose"],
                kwargs["interactive"]
            )
        )
        options["context"].load_config(kwargs["config"].read())

        return func(options, *args, **kwargs)
    return wrapper
