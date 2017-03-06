import click

from ...actions.build import Action
from ..common import common_parameters


@click.command()
@common_parameters
@click.option(
    "-o", "--outline", is_flag=True,
    help="Print an outline of what steps will be "
         "taken to build the stacks"
)
@click.option(
    "--force", multiple=True, type=str, metavar="STACKNAME",
    help="If a stackname is provided to --force, it "
         "will be updated, even if it is locked in "
         "the config."
)
@click.option(
    "--stacks", multiple=True, type=str, metavar="STACKNAME",
    help="Only work on the stacks given. Can be "
         "specified more than once. If not specified "
         "then stacker will work on all stacks in the "
         "config file."
)
@click.option(
    "-t", "--tail", is_flag=True,
    help="Tail the CloudFormation logs while working"
         "with stacks"
)
@click.option(
    "-d", "--dump", is_flag=True,
    help="Dump the rendered Cloudformation templates "
         "to a directory"
)
@click.pass_obj
def build(options, *args, **kwargs):
    """Launches or updates CloudFormation stacks based on the given config.

    Stacker is smart enough to figure out if anything (the template or
    parameters) have changed for a given stack. If nothing has changed,
    stacker will correctly skip executing anything against the stack.

    """

    options["context"].stack_names = kwargs["stacks"]
    options["context"].force_stacks = kwargs["force"]

    build = Action(
        options["context"],
        provider=options["provider"]
    )
    build.execute(
        outline=kwargs["outline"],
        tail=kwargs["tail"],
        dump=kwargs["dump"]
    )
