from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
from collections import Mapping, namedtuple

from stacker.exceptions import HookExecutionFailed
from stacker.util import load_object_from_string


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
        self.args = args or {}
        self.required_by = set(required_by or [])
        self.requires = set(requires or [])
        self.profile = profile
        self.region = region

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

        data_key = self.data_key
        required = self.required
        kwargs = self.args or {}
        enabled = self.enabled

        if not enabled:
            logger.debug("Hook %s is disabled, skipping", self.name)
            return

        try:
            method = load_object_from_string(self.path)
        except (AttributeError, ImportError) as e:
            logger.exception("Unable to load method at %s for hook %s:",
                             self.path, self.name)
            if required:
                raise HookExecutionFailed(self, exception=e)

            return

        try:
            result = method(context=context, provider=provider, **kwargs)
        except Exception as e:
            if required:
                raise HookExecutionFailed(self, exception=e)

            return

        if not result:
            if required:
                raise HookExecutionFailed(self, result=result)

            logger.warning("Non-required hook %s failed. Return value: %s",
                           self.name, result)
            return result

        if isinstance(result, Mapping):
            if data_key:
                logger.debug("Adding result for hook %s to context in "
                             "data_key %s.", self.name, data_key)
                context.set_hook_data(data_key, result)

        return result


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
