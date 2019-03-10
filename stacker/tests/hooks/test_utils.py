from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()

import unittest

import queue

from stacker.config import Hook
from stacker.hooks.utils import handle_hooks

from ..factories import (
    mock_context,
    mock_provider,
)

hook_queue = queue.Queue()


def mock_hook(*args, **kwargs):
    hook_queue.put(kwargs)
    return True


def fail_hook(*args, **kwargs):
    return None


def exception_hook(*args, **kwargs):
    raise Exception


def context_hook(*args, **kwargs):
    return "context" in kwargs


def result_hook(*args, **kwargs):
    return {"foo": "bar"}


def kwargs_hook(*args, **kwargs):
    return kwargs


class TestHooks(unittest.TestCase):

    def setUp(self):
        self.context = mock_context(namespace="namespace")
        self.provider = mock_provider(region="us-east-1")

    def test_empty_hook_stage(self):
        hooks = []
        handle_hooks("fake", hooks, self.provider, self.context)
        self.assertTrue(hook_queue.empty())

    def test_missing_required_hook(self):
        hooks = [Hook({"path": "not.a.real.path", "required": True})]
        with self.assertRaises(ImportError):
            handle_hooks("missing", hooks, self.provider, self.context)

    def test_missing_required_hook_method(self):
        hooks = [{"path": "stacker.hooks.blah", "required": True}]
        with self.assertRaises(AttributeError):
            handle_hooks("missing", hooks, self.provider, self.context)

    def test_missing_non_required_hook_method(self):
        hooks = [Hook({"path": "stacker.hooks.blah", "required": False})]
        handle_hooks("missing", hooks, self.provider, self.context)
        self.assertTrue(hook_queue.empty())

    def test_default_required_hook(self):
        hooks = [Hook({"path": "stacker.hooks.blah"})]
        with self.assertRaises(AttributeError):
            handle_hooks("missing", hooks, self.provider, self.context)

    def test_valid_hook(self):
        hooks = [
            Hook({"path": "stacker.tests.hooks.test_utils.mock_hook",
                  "required": True})]
        handle_hooks("missing", hooks, self.provider, self.context)
        good = hook_queue.get_nowait()
        self.assertEqual(good["provider"].region, "us-east-1")
        with self.assertRaises(queue.Empty):
            hook_queue.get_nowait()

    def test_valid_enabled_hook(self):
        hooks = [
            Hook({"path": "stacker.tests.hooks.test_utils.mock_hook",
                  "required": True, "enabled": True})]
        handle_hooks("missing", hooks, self.provider, self.context)
        good = hook_queue.get_nowait()
        self.assertEqual(good["provider"].region, "us-east-1")
        with self.assertRaises(queue.Empty):
            hook_queue.get_nowait()

    def test_valid_enabled_false_hook(self):
        hooks = [
            Hook({"path": "stacker.tests.hooks.test_utils.mock_hook",
                  "required": True, "enabled": False})]
        handle_hooks("missing", hooks, self.provider, self.context)
        self.assertTrue(hook_queue.empty())

    def test_context_provided_to_hook(self):
        hooks = [
            Hook({"path": "stacker.tests.hooks.test_utils.context_hook",
                  "required": True})]
        handle_hooks("missing", hooks, "us-east-1", self.context)

    def test_hook_failure(self):
        hooks = [
            Hook({"path": "stacker.tests.hooks.test_utils.fail_hook",
                  "required": True})]
        with self.assertRaises(SystemExit):
            handle_hooks("fail", hooks, self.provider, self.context)
        hooks = [{"path": "stacker.tests.hooks.test_utils.exception_hook",
                  "required": True}]
        with self.assertRaises(Exception):
            handle_hooks("fail", hooks, self.provider, self.context)
        hooks = [
            Hook({"path": "stacker.tests.hooks.test_utils.exception_hook",
                  "required": False})]
        # Should pass
        handle_hooks("ignore_exception", hooks, self.provider, self.context)

    def test_return_data_hook(self):
        hooks = [
            Hook({
                "path": "stacker.tests.hooks.test_utils.result_hook",
                "data_key": "my_hook_results"
            }),
            # Shouldn't return data
            Hook({
                "path": "stacker.tests.hooks.test_utils.context_hook"
            })
        ]
        handle_hooks("result", hooks, "us-east-1", self.context)

        self.assertEqual(
            self.context.hook_data["my_hook_results"]["foo"],
            "bar"
        )
        # Verify only the first hook resulted in stored data
        self.assertEqual(
            list(self.context.hook_data.keys()), ["my_hook_results"]
        )

    def test_return_data_hook_duplicate_key(self):
        hooks = [
            Hook({
                "path": "stacker.tests.hooks.test_utils.result_hook",
                "data_key": "my_hook_results"
            }),
            Hook({
                "path": "stacker.tests.hooks.test_utils.result_hook",
                "data_key": "my_hook_results"
            })
        ]

        with self.assertRaises(KeyError):
            handle_hooks("result", hooks, "us-east-1", self.context)

    def test_resolve_lookups_in_args(self):
        hooks = [
            Hook({
                "path": "stacker.tests.hooks.test_utils.kwargs_hook",
                "data_key": "my_hook_results",
                "args": {
                    "default_lookup": "${default env_var::default_value}"
                }
            })
        ]
        handle_hooks("lookups", hooks, "us-east-1", self.context)

        self.assertEqual(
            self.context.hook_data["my_hook_results"]["default_lookup"],
            "default_value"
        )
