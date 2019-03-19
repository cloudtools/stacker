from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
from collections import Mapping, namedtuple

from stacker.exceptions import HookExecutionFailed, StackDoesNotExist
from stacker.util import load_object_from_string
from stacker.status import (
    COMPLETE, SKIPPED, FailedStatus, NotSubmittedStatus, SkippedStatus
)
from stacker.variables import Variable

logger = logging.getLogger(__name__)


def no_op(*args, **kwargs):
    logger.info("No-op hook called with arguments: {}".format(kwargs))
    return True


class Hook(object):
    @classmethod
    def from_definition(cls, definition, name_fallback=None):
        """Create a hook instance from a config definition"""
        name = definition.name or name_fallback
        if not name:
            raise ValueError('Hook definition does not include name and no '
                             'fallback provided')

        data_key = definition.data_key or name
        return cls(
            name=name,
            path=definition.path,
            required=definition.required,
            enabled=definition.enabled,
            data_key=data_key,
            args=definition.args,
            required_by=definition.required_by,
            requires=definition.requires,
            profile=definition.profile,
            region=definition.region)

    def __init__(self, name, path, required=True, enabled=True,
                 data_key=None, args=None, required_by=None, requires=None,
                 profile=None, region=None):
        self.path = path
        self.name = name
        self.required = required
        self.enabled = enabled
        self.data_key = data_key
        self.args = args
        self.required_by = set(required_by or [])
        self.requires = set(requires or [])
        self.profile = profile
        self.region = region

        self._args = {}
        self._args, deps = self.parse_args(args)
        self.requires.update(deps)

        self._callable = self.resolve_path()

    def parse_args(self, args):
        arg_vars = {}
        deps = set()

        if args:
            for key, value in args.items():
                var = arg_vars[key] = \
                    Variable('{}.args.{}'.format(self.name, key), value)
                deps.update(var.dependencies())

        return arg_vars, deps

    def resolve_path(self):
        try:
            return load_object_from_string(self.path)
        except (AttributeError, ImportError) as e:
            raise ValueError("Unable to load method at %s for hook %s: %s",
                             self.path, self.name, str(e))

    def check_args_dependencies(self, provider, context):
        # When running hooks for destruction, we might rely on outputs of
        # stacks that we assume have been deployed. Unfortunately, since
        # destruction must happen in the reverse order of creation, those stack
        # dependencies will not be present on `requires`, but in `required_by`,
        # meaning the execution engine won't stop the hook from running early.

        # To deal with that, manually find the dependencies coming from
        # lookups in the hook arguments, select those that represent stacks,
        # and check if they are actually available.

        dependencies = set()
        for value in self._args.values():
            dependencies.update(value.dependencies())

        for dep in dependencies:
            # We assume all dependency names are valid here. Hence, if we can't
            # find a stack with that same name, it must be a target or a hook,
            # and hence we don't need to check it
            stack = context.get_stack(dep)
            if stack is None:
                continue

            # This will raise if the stack is missing
            provider.get_stack(stack.fqn)

    def resolve_args(self, provider, context):
        for key, value in self._args.items():
            value.resolve(context, provider)
            yield key, value.value

    def run(self, provider, context):
        """Run a Hook and capture its result

        These are pieces of external code that we want to run in addition to
        CloudFormation deployments, to perform actions that are not easily
        handled in a template.

        Args:
            provider (:class:`stacker.provider.base.BaseProvider`):
                Provider to pass to the hook
            context (:class:`stacker.context.Context`): The current stacker
                context
        Raises:
            :class:`stacker.exceptions.HookExecutionFailed`:
                if the hook failed
        Returns: the result of the hook if it was run, ``None`` if it was
            skipped.
        """

        logger.info("Executing hook %s", self)
        kwargs = dict(self.resolve_args(provider, context))
        try:
            result = self._callable(context=context, provider=provider,
                                    **kwargs)
        except Exception as e:
            if self.required:
                raise HookExecutionFailed(self, cause=e)

            return None

        if not result:
            if self.required:
                raise HookExecutionFailed(self, result=result)

            logger.warning("Non-required hook %s failed. Return value: %s",
                           self.name, result)
            return result

        if isinstance(result, Mapping):
            if self.data_key:
                logger.debug("Adding result for hook %s to context in "
                             "data_key %s.", self.name, self.data_key)
                context.set_hook_data(self.data_key, result)

        return result

    def run_step(self, provider_builder, context):
        if not self.enabled:
            return NotSubmittedStatus()

        provider = provider_builder.build(profile=self.profile,
                                          region=self.region)

        try:
            self.check_args_dependencies(provider, context)
        except StackDoesNotExist as e:
            reason = "required stack not deployed: {}".format(e.stack_name)
            return SkippedStatus(reason=reason)

        try:
            result = self.run(provider, context)
        except HookExecutionFailed as e:
            return FailedStatus(reason=str(e))

        if not result:
            return SKIPPED

        return COMPLETE

    def __str__(self):
        return 'Hook(name={}, path={}, profile={}, region={})'.format(
            self.name, self.path, self.profile, self.region)


class ActionHooks(namedtuple('ActionHooks', 'action_name pre post custom')):
    @classmethod
    def from_config(cls, config, action_name):
        def from_key(key):
            for i, hook_def in enumerate(config.get(key) or [], 1):
                name_fallback = '{}_{}_{}'.format(key, i, hook_def.path)
                yield Hook.from_definition(hook_def,
                                           name_fallback=name_fallback)

        return ActionHooks(
            action_name=action_name,
            pre=list(from_key('pre_{}'.format(action_name))),
            post=list(from_key('post_{}'.format(action_name))),
            custom=list(from_key('{}_hooks'.format(action_name))))
