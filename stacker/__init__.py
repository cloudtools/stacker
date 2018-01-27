from stacker.plan2 import Step, build_plan

__version__ = "1.1.4"


def plan(description=None, action=None,
         tail=None,
         stacks=None, stack_names=None,
         reverse=False):
    """A simple helper that builds a graph based plan from a set of stacks."""

    steps = [
        Step(stack, fn=action, watch_func=tail)
        for stack in stacks]

    return build_plan(
        description=description,
        steps=steps,
        step_names=stack_names,
        reverse=reverse)
