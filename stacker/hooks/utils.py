import os
import sys
import collections.abc
import logging

from stacker.util import load_object_from_string

logger = logging.getLogger(__name__)


def full_path(path):
    return os.path.abspath(os.path.expanduser(path))


def handle_hooks(stage, hooks, provider, context):
    """ Used to handle pre/post_build hooks.

    These are pieces of code that we want to run before/after the builder
    builds the stacks.

    Args:
        stage (string): The current stage (pre_run, post_run, etc).
        hooks (list): A list of :class:`stacker.config.Hook` containing the
            hooks to execute.
        provider (:class:`stacker.provider.base.BaseProvider`): The provider
            the current stack is using.
        context (:class:`stacker.context.Context`): The current stacker
            context.
    """
    if not hooks:
        logger.debug("No %s hooks defined.", stage)
        return

    hook_paths = []
    for i, h in enumerate(hooks):
        try:
            hook_paths.append(h.path)
        except KeyError:
            raise ValueError("%s hook #%d missing path." % (stage, i))

    logger.info("Executing %s hooks: %s", stage, ", ".join(hook_paths))
    for hook in hooks:
        data_key = hook.data_key
        required = hook.required
        kwargs = hook.args or {}
        enabled = hook.enabled
        if not enabled:
            logger.debug("hook with method %s is disabled, skipping",
                         hook.path)
            continue
        try:
            method = load_object_from_string(hook.path)
        except (AttributeError, ImportError):
            logger.exception("Unable to load method at %s:", hook.path)
            if required:
                raise
            continue
        try:
            result = method(context=context, provider=provider, **kwargs)
        except Exception:
            logger.exception("Method %s threw an exception:", hook.path)
            if required:
                raise
            continue
        if not result:
            if required:
                logger.error("Required hook %s failed. Return value: %s",
                             hook.path, result)
                sys.exit(1)
            logger.warning("Non-required hook %s failed. Return value: %s",
                           hook.path, result)
        else:
            if isinstance(result, collections.abc.Mapping):
                if data_key:
                    logger.debug("Adding result for hook %s to context in "
                                 "data_key %s.", hook.path, data_key)
                    context.set_hook_data(data_key, result)
                else:
                    logger.debug("Hook %s returned result data, but no data "
                                 "key set, so ignoring.", hook.path)
