import click

from ... import __version__
from .build import build

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    ctx.obj = {}


cli.add_command(build)
