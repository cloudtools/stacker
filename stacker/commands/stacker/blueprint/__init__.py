"""Stacker subcommands for working with blueprints."""
from ..base import BaseCommand

from .info import Info


class Blueprint(BaseCommand):

    name = "blueprint"
    subcommands = (Info,)

    def add_arguments(self, parser):
        # we don't need global arguments
        pass
