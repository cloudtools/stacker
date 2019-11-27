from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import os
import json
import logging
import time
import uuid
import threading

from .util import stack_template_key_name, merge_map
from .exceptions import (
    CancelExecution,
    GraphError,
    PlanFailed,
    PersistentGraphLocked
)
from .ui import ui
from .dag import DAG, DAGValidationError, walk
from .status import (
    SkippedStatus,
    FailedStatus,
    PENDING,
    SUBMITTED,
    COMPLETE,
    SKIPPED,
    FAILED,
)

logger = logging.getLogger(__name__)

COLOR_CODES = {
    SUBMITTED.code: 33,  # yellow
    COMPLETE.code: 32,   # green
    FAILED.code: 31,     # red
}


def json_serial(obj):
    """Serialize json.

    Args:
        obj (Any): A python object.

    Example:
        json.dumps(data, default=json_serial)

    """
    if isinstance(obj, set):
        return list(obj)
    raise TypeError


def log_step(step):
    msg = "%s: %s" % (step, step.status.name)
    if step.status.reason:
        msg += " (%s)" % (step.status.reason)
    color_code = COLOR_CODES.get(step.status.code, 37)
    ui.info(msg, extra={"color": color_code})


def merge_graphs(graph1, graph2):
    """Combine two Graphs into one, retaining steps.

    Args:
        graph1 (:class:`Graph`): Graph that ``graph2`` will
            be merged into.
        graph2 (:class:`Graph`): Graph that will be merged
            into ``graph1``.

    Returns:
        (:class:`Graph`) A combined graph.

    """
    merged_graph_dict = merge_map(graph1.to_dict().copy(),
                                  graph2.to_dict())
    steps = [graph1.steps.get(name, graph2.steps.get(name))
             for name in merged_graph_dict.keys()]
    return Graph.from_steps(steps)


class Step(object):
    """State machine for executing generic actions related to stacks.

    Args:
        stack (:class:`Stack`): the stack associated with this step.
        fn (Callable): the function to run to execute the step. This
            function will be ran multiple times until the step is "done".
        watch_func (Callable): an optional function that will be called
            to "tail" the step action.

    """

    def __init__(self, stack, fn=None, watch_func=None):
        self.stack = stack
        self.status = PENDING
        self.last_updated = time.time()
        self.fn = fn
        self.watch_func = watch_func

    def __repr__(self):
        return "<stacker.plan.Step:%s>" % (self.stack.name,)

    def __str__(self):
        return self.stack.name

    def run(self):
        """Runs this step until it has completed successfully, or been
        skipped.
        """

        stop_watcher = threading.Event()
        watcher = None
        if self.watch_func:
            watcher = threading.Thread(
                target=self.watch_func,
                args=(self.stack, stop_watcher)
            )
            watcher.start()

        try:
            while not self.done:
                self._run_once()
        finally:
            if watcher:
                stop_watcher.set()
                watcher.join()
        return self.ok

    def _run_once(self):
        try:
            status = self.fn(self.stack, status=self.status)
        except CancelExecution:
            status = SkippedStatus('canceled execution')
        except Exception as err:
            logger.exception(err)
            status = FailedStatus(reason=str(err))
        self.set_status(status)
        return status

    @property
    def name(self):
        return self.stack.name

    @property
    def requires(self):
        return self.stack.requires

    @property
    def required_by(self):
        return self.stack.required_by

    @property
    def completed(self):
        """Returns True if the step is in a COMPLETE state."""
        return self.status == COMPLETE

    @property
    def skipped(self):
        """Returns True if the step is in a SKIPPED state."""
        return self.status == SKIPPED

    @property
    def failed(self):
        """Returns True if the step is in a FAILED state."""
        return self.status == FAILED

    @property
    def done(self):
        """Returns True if the step is finished (either COMPLETE, SKIPPED or FAILED)
        """
        return self.completed or self.skipped or self.failed

    @property
    def ok(self):
        """Returns True if the step is finished (either COMPLETE or SKIPPED)"""
        return self.completed or self.skipped

    @property
    def submitted(self):
        """Returns True if the step is SUBMITTED, COMPLETE, or SKIPPED."""
        return self.status >= SUBMITTED

    def set_status(self, status):
        """Sets the current step's status.
        Args:
            status (:class:`Status <Status>` object): The status to set the
                step to.
        """
        if status is not self.status:
            logger.debug("Setting %s state to %s.", self.stack.name,
                         status.name)
            self.status = status
            self.last_updated = time.time()
            if self.stack.logging:
                log_step(self)

    def complete(self):
        """A shortcut for set_status(COMPLETE)"""
        self.set_status(COMPLETE)

    def skip(self):
        """A shortcut for set_status(SKIPPED)"""
        self.set_status(SKIPPED)

    def submit(self):
        """A shortcut for set_status(SUBMITTED)"""
        self.set_status(SUBMITTED)

    @classmethod
    def from_stack_name(cls, stack_name, context, requires=None, fn=None,
                        watch_func=None):
        """Create a step using only a stack name.

        Args:
            stack_name (str): Name of a CloudFormation stack.
            context (:class:`stacker.context.Context`): Context object.
                Required to initialize a "fake" :class:`stacker.stack.Stack`.
            requires (List[str]): Stacks that this stack depends on.
            fn (Callable): The function to run to execute the step.
                This function will be ran multiple times until the step
                is "done".
            watch_func (Callable): an optional function that will be
                called to "tail" the step action.

        Returns:
            (:class:`Step`)

        """
        from stacker.config import Stack as StackConfig
        from stacker.stack import Stack

        stack_def = StackConfig({'name': stack_name,
                                 'requires': requires or []})
        stack = Stack(stack_def, context)
        return cls(stack, fn=fn, watch_func=watch_func)

    @classmethod
    def from_persistent_graph(cls, graph_dict, context, fn=None,
                              watch_func=None):
        """Create a steps for a persistent graph dict.

        Args:
            graph_dict (Dict[str, List[str]]): A graph dict.
            context (:class:`stacker.context.Context`): Context object.
                Required to initialize a "fake" :class:`stacker.stack.Stack`.
            requires (List[str]): Stacks that this stack depends on.
            fn (Callable): The function to run to execute the step.
                This function will be ran multiple times until the step
                is "done".
            watch_func (Callable): an optional function that will be
                called to "tail" the step action.

        Returns:
            (List[:class:`Step`])

        """
        steps = []

        for name, requires in graph_dict.items():
            steps.append(cls.from_stack_name(name, context, requires,
                                             fn, watch_func))
        return steps


class Graph(object):
    """Graph represents a graph of steps.

    The :class:`Graph` helps organize the steps needed to execute a particular
    action for a set of :class:`stacker.stack.Stack` objects. When initialized
    with a set of steps, it will first build a Directed Acyclic Graph from the
    steps and their dependencies.

    Example:

    >>> dag = DAG()
    >>> a = Step("a", fn=build)
    >>> b = Step("b", fn=build)
    >>> dag.add_step(a)
    >>> dag.add_step(b)
    >>> dag.connect(a, b)

    Args:
        steps (List[:class:`Step`]): an optional list of :class:`Step`
            objects to execute.
        dag (:class:`stacker.dag.DAG`): an optional :class:`stacker.dag.DAG`
            object. If one is not provided, a new one will be initialized.

    """

    def __str__(self):
        return self.dumps()

    def __init__(self, steps=None, dag=None):
        self.steps = steps or {}
        self.dag = dag or DAG()

    def add_step(self, step, add_dependencies=False, add_dependants=False):
        """Add a step to the graph.

        Args:
            step (:class:`Step`): The step to be added.
            add_dependencies (bool): Connect steps that need to be completed
                before this step.
            add_dependants (bool): Connect steps that require this step.

        """
        self.steps[step.name] = step
        self.dag.add_node(step.name)

        if add_dependencies:
            for dep in step.requires:
                self.connect(step.name, dep)

        if add_dependants:
            for parent in step.required_by:
                self.connect(parent, step.name)

    def add_step_if_not_exists(self, step, add_dependencies=False,
                               add_dependants=False):
        """Try to add a step to the graph.

        Can be used when failure to add is acceptable.

        Args:
            step (:class:`Step`): The step to be added.
            add_dependencies (bool): Connect steps that need to be completed
                before this step.
            add_dependants (bool): Connect steps that require this step.

        """
        if self.steps.get(step.name):
            return

        self.steps[step.name] = step
        self.dag.add_node_if_not_exists(step.name)

        if add_dependencies:
            for dep in step.requires:
                try:
                    self.connect(step.name, dep)
                except GraphError:
                    continue

        if add_dependants:
            for parent in step.required_by:
                try:
                    self.connect(parent, step.name)
                except GraphError:
                    continue

    def add_steps(self, steps):
        """Add a list of steps.

        Args:
            steps (List[:class:`Step`]): The step to be added.

        """
        for step in steps:
            self.add_step(step)

        for step in steps:
            for dep in step.requires:
                self.connect(step.name, dep)

            for parent in step.required_by:
                self.connect(parent, step.name)

    def pop(self, step, default=None):
        """Remove a step from the graph.

        Args:
            step: (:class:`Step`): The step to remove from the graph.
            default (Any): Returned if the step could not be popped

        Returns:
            (Any)

        """
        self.dag.delete_node_if_exists(step.name)
        return self.steps.pop(step.name, default)

    def connect(self, step, dep):
        try:
            self.dag.add_edge(step, dep)
        except KeyError as e:
            raise GraphError(e, step, dep)
        except DAGValidationError as e:
            raise GraphError(e, step, dep)

    def transitive_reduction(self):
        self.dag.transitive_reduction()

    def walk(self, walker, walk_func):
        def fn(step_name):
            step = self.steps[step_name]
            return walk_func(step)

        return walker(self.dag, fn)

    def downstream(self, step_name):
        """Returns the direct dependencies of the given step"""
        return list(self.steps[dep] for dep in self.dag.downstream(step_name))

    def transposed(self):
        """Returns a "transposed" version of this graph. Useful for walking in
        reverse.
        """
        return Graph(steps=self.steps, dag=self.dag.transpose())

    def filtered(self, step_names):
        """Returns a "filtered" version of this graph."""
        return Graph(steps=self.steps, dag=self.dag.filter(step_names))

    def topological_sort(self):
        nodes = self.dag.topological_sort()
        return [self.steps[step_name] for step_name in nodes]

    def to_dict(self):
        return self.dag.graph

    def dumps(self, indent=None):
        """Output the graph as a json seralized string for storage.

        Args:
            indent (Optional[int]): Number of spaces for each indentation.

        Returns:
            (str)

        """
        return json.dumps(self.to_dict(), default=json_serial, indent=indent)

    @classmethod
    def from_dict(cls, graph_dict, context):
        """Create a Graph from a graph dict.

        Args:
            graph_dict (Dict[str, List[str]]): The dictionary used to
                create the graph.
            context (:class:`stacker.context.Context`): Required to init
                stacks.

        Returns:
            (:class:`Graph`)

        """
        return cls.from_steps(Step.from_persistent_graph(graph_dict, context))

    @classmethod
    def from_steps(cls, steps):
        """Create a Graph from Steps.

        Args:
            steps (List[:class:`Step`]): Steps used to create the graph.

        Returns:
            (:class:`Graph`)

        """
        graph = cls()
        graph.add_steps(steps)
        return graph


class Plan(object):
    """A convenience class for working on a Graph.

    Args:
        description (str): description of the plan.
        graph (:class:`Graph`): a graph of steps.

    """

    def __str__(self):
        return self.graph.dumps()

    def __init__(self, description, graph, context=None,
                 reverse=False, require_unlocked=True):
        """Initialize class.

        Args:
            description (str): Description of what the plan is going to do.
            graph (:class:`Graph`): Local graph used for the plan.
            context (:class:`stacker.context.Context`): Context object.
            reverse (bool): Transpose the graph for walking in reverse.
            require_unlocked (bool): Require the persistent graph to be
                unlocked before executing steps.

        """
        self.context = context
        self.description = description
        self.id = uuid.uuid4()
        self.reverse = reverse
        self.require_unlocked = require_unlocked

        if self.reverse:
            graph = graph.transposed()

        if self.context:
            self.locked = self.context.persistent_graph_locked

            if self.context.stack_names:
                nodes = []
                for target in self.context.stack_names:
                    if graph.steps.get(target):
                        nodes.append(target)
                graph = graph.filtered(nodes)
        else:
            self.locked = False
        self.graph = graph

    def outline(self, level=logging.INFO, message=""):
        """Print an outline of the actions the plan is going to take.
        The outline will represent the rough ordering of the steps that will be
        taken.

        Args:
            level (int, optional): a valid log level that should be used to log
                the outline
            message (str, optional): a message that will be logged to
                the user after the outline has been logged.

        """
        steps = 1
        logger.log(level, "Plan \"%s\":", self.description)
        for step in self.steps:
            logger.log(
                level,
                "  - step: %s: target: \"%s\", action: \"%s\"",
                steps,
                step.name,
                step.fn.__name__,
            )
            steps += 1

        if message:
            logger.log(level, message)

    def dump(self, directory, context, provider=None):
        logger.info("Dumping \"%s\"...", self.description)
        directory = os.path.expanduser(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)

        def walk_func(step):
            step.stack.resolve(
                context=context,
                provider=provider,
            )
            blueprint = step.stack.blueprint
            filename = stack_template_key_name(blueprint)
            path = os.path.join(directory, filename)

            blueprint_dir = os.path.dirname(path)
            if not os.path.exists(blueprint_dir):
                os.makedirs(blueprint_dir)

            logger.info("Writing stack \"%s\" -> %s", step.name, path)
            with open(path, "w") as f:
                f.write(blueprint.rendered)

            return True

        return self.graph.walk(walk, walk_func)

    def execute(self, *args, **kwargs):
        """Walks each step in the underlying graph, and raises an exception if
        any of the steps fail.

        Raises:
            PersistentGraphLocked: Raised if the persistent graph is
                locked prior to execution and this session did not lock it.
            PlanFailed: Raised if any of the steps fail.

        """
        if self.locked and self.require_unlocked:
            raise PersistentGraphLocked

        self.walk(*args, **kwargs)

        failed_steps = [step for step in self.steps if step.status == FAILED]
        if failed_steps:
            raise PlanFailed(failed_steps)

    def walk(self, walker):
        """Walks each step in the underlying graph, in topological order.

        Args:
            walker (func): a walker function to be passed to
                :class:`stacker.dag.DAG` to walk the graph.
        """

        def walk_func(step):
            """Execute a :class:`Step` wile walking the graph.

            Handles updating the persistent graph if one is being used.

            Args:
                step (:class:`Step`): :class:`Step` to execute.

            Returns:
                (bool)

            """
            # Before we execute the step, we need to ensure that it's
            # transitive dependencies are all in an "ok" state. If not, we
            # won't execute this step.
            for dep in self.graph.downstream(step.name):
                if not dep.ok:
                    step.set_status(FailedStatus("dependency has failed"))
                    return step.ok

            result = step.run()

            if not self.context or not self.context.persistent_graph:
                return result

            if (step.completed or
                    (step.skipped and
                     step.status.reason == ('does not exist in '
                                            'cloudformation'))):
                if step.fn.__name__ == '_destroy_stack':
                    self.context.persistent_graph.pop(step)
                    logger.debug("Removed step '%s' from the persistent graph",
                                 step.name)
                elif step.fn.__name__ == '_launch_stack':
                    self.context.persistent_graph.add_step_if_not_exists(
                        step, add_dependencies=True, add_dependants=True
                    )
                    logger.debug("Added step '%s' to the persistent graph",
                                 step.name)
                else:
                    return result
                self.context.put_persistent_graph(self.lock_code)

        return self.graph.walk(walker, walk_func)

    @property
    def lock_code(self):
        """Used for locking/unlocking the persistent graph.

        Returns:
            (str)

        """
        return str(self.id)

    @property
    def steps(self):
        steps = self.graph.topological_sort()
        steps.reverse()
        return steps

    @property
    def step_names(self):
        return [step.name for step in self.steps]

    def keys(self):
        return self.step_names
