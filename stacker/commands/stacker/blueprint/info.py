"""Get info for a blueprint"""
import logging

from ..base import BaseCommand
from ....blueprints.info import explain_path

logger = logging.getLogger(__name__)


class Info(BaseCommand):

    name = "info"
    description = "info description"

    def add_arguments(self, parser):
        # we don't want global arguments so we're intentionally not calling
        # super
        parser.add_argument("path", metavar="BLUEPRINT_PATH", type=str,
                            help="The path to the blueprint you want info on")

    def run(self, options, **kwargs):
        super(Info, self).run(options, **kwargs)
        explain_path(options.path)
