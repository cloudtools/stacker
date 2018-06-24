from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import logging
import sys
import json

from .base import BaseAction, plan


logger = logging.getLogger(__name__)


def each_step(graph):
    """Returns an iterator that yields each step and it's direct
    dependencies.
    """

    steps = graph.topological_sort()
    steps.reverse()

    for step in steps:
        deps = graph.downstream(step.name)
        yield (step, deps)


def dot_format(out, graph, name="digraph"):
    """Outputs the graph using the graphviz "dot" format."""

    out.write("digraph %s {\n" % name)
    for step, deps in each_step(graph):
        for dep in deps:
            out.write("  \"%s\" -> \"%s\";\n" % (step, dep))

    out.write("}\n")


def json_format(out, graph):
    """Outputs the graph in a machine readable JSON format."""
    steps = {}
    for step, deps in each_step(graph):
        steps[step.name] = {}
        steps[step.name]["deps"] = [dep.name for dep in deps]

    json.dump({"steps": steps}, out, indent=4)
    out.write("\n")


FORMATTERS = {
    "dot": dot_format,
    "json": json_format,
}


class Action(BaseAction):

    def _generate_plan(self):
        return plan(
            description="Print graph",
            action=None,
            stacks=self.context.get_stacks(),
            targets=self.context.stack_names)

    def run(self, format=None, reduce=False, *args, **kwargs):
        """Generates the underlying graph and prints it.

        """
        plan = self._generate_plan()
        if reduce:
            # This will performa a transitive reduction on the underlying
            # graph, producing less edges. Mostly useful for the "dot" format,
            # when converting to PNG, so it creates a prettier/cleaner
            # dependency graph.
            plan.graph.transitive_reduction()

        fn = FORMATTERS[format]
        fn(sys.stdout, plan.graph)
        sys.stdout.flush()
