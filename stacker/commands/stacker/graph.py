"""Prints the the relationships between steps as a graph.

"""

from .base import BaseCommand
from ...actions import graph


class Graph(BaseCommand):

    name = "graph"
    description = __doc__

    def add_arguments(self, parser):
        super(Graph, self).add_arguments(parser)
        parser.add_argument("-f", "--format", default="dot",
                            choices=list(graph.FORMATTERS.iterkeys()),
                            help="The format to print the graph in.")
        parser.add_argument("--reduce", action="store_true",
                            help="When provided, this will create a "
                                 "graph with less edges, by performing "
                                 "a transitive reduction on the underlying "
                                 "graph. While this will produce a less "
                                 "noisy graph, it is slower.")

    def run(self, options, **kwargs):
        super(Graph, self).run(options, **kwargs)
        action = graph.Action(options.context,
                              provider_builder=options.provider_builder)
        action.execute(
            format=options.format,
            reduce=options.reduce)
