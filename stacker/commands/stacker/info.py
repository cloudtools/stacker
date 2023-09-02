"""Gets information on the CloudFormation stacks based on the given config."""

from .base import BaseCommand
from ...actions import info


class Info(BaseCommand):

    name = "info"
    description = __doc__

    def add_arguments(self, parser):
        super(Info, self).add_arguments(parser)
        parser.add_argument("--stacks", action="append",
                            metavar="STACKNAME", type=str,
                            help="Only work on the stacks given. Can be "
                                 "specified more than once. If not specified "
                                 "then stacker will work on all stacks in the "
                                 "config file.")
        parser.add_argument("--output-format", action="store", type=str,
                            choices=info.OUTPUT_FORMATS,
                            help="Write out stack information in the given "
                                 "export format. Use it if you intend to "
                                 "parse the result programatically.")

    def run(self, options, **kwargs):
        super(Info, self).run(options, **kwargs)
        action = info.Action(options.context,
                             provider_builder=options.provider_builder)

        action.execute(output_format=options.output_format)

    def get_context_kwargs(self, options, **kwargs):
        return {"stack_names": options.stacks}
