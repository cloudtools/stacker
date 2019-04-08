from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
import mock


from stacker.exceptions import HookExecutionFailed
from stacker.hooks import Hook
from stacker.status import (
    COMPLETE, FailedStatus, NotSubmittedStatus, SkippedStatus
)
from .factories import MockProviderBuilder, mock_context, mock_provider


mock_hook = mock.Mock()


class TestHooks(unittest.TestCase):
    mock_hook_path = __name__ + ".mock_hook"

    def setUp(self):
        self.context = mock_context(extra_config_args={
            "stacks": [
                {"name": "undeployed-stack", "template_path": "missing"}
            ]
        })
        self.provider = mock_provider(region="us-east-1")
        self.provider_builder = MockProviderBuilder(self.provider)

        global mock_hook
        mock_hook = mock.Mock()

    def test_missing_module(self):
        with self.assertRaises(ValueError):
            Hook("test", path="not.a.real.path")

    def test_missing_method(self):
        with self.assertRaises(ValueError):
            Hook("test", path=self.mock_hook_path + "garbage")

    def test_valid_enabled_hook(self):
        hook = Hook("test", path=self.mock_hook_path,
                    required=True, enabled=True)

        result = mock_hook.return_value = mock.Mock()
        self.assertIs(result, hook.run(self.provider, self.context))
        mock_hook.assert_called_once()

    def test_context_provided_to_hook(self):
        hook = Hook("test", path=self.mock_hook_path,
                    required=True)

        def return_context(*args, **kwargs):
            return kwargs['context']

        mock_hook.side_effect = return_context
        result = hook.run(self.provider, self.context)
        self.assertIs(result, self.context)

    def test_hook_failure(self):
        hook = Hook("test", path=self.mock_hook_path,
                    required=True)

        err = Exception()
        mock_hook.side_effect = err

        with self.assertRaises(HookExecutionFailed) as raised:
            hook.run(self.provider, self.context)

        self.assertIs(hook, raised.exception.hook)
        self.assertIs(err, raised.exception.cause)

    def test_hook_failure_skip(self):
        hook = Hook("test", path=self.mock_hook_path,
                    required=False)

        mock_hook.side_effect = Exception()
        result = hook.run(self.provider, self.context)
        self.assertIsNone(result)

    def test_return_data_hook(self):
        hook = Hook("test", path=self.mock_hook_path,
                    data_key='test')
        hook_data = {'hello': 'world'}
        mock_hook.return_value = hook_data

        result = hook.run(self.provider, self.context)
        self.assertEqual(hook_data, result)
        self.assertEqual(hook_data, self.context.hook_data.get('test'))

    def test_return_data_hook_duplicate_key(self):
        hook = Hook("test", path=self.mock_hook_path,
                    data_key='test')
        mock_hook.return_value = {'foo': 'bar'}

        hook_data = {'hello': 'world'}
        self.context.set_hook_data('test', hook_data)
        with self.assertRaises(KeyError):
            hook.run(self.provider, self.context)

        self.assertEqual(hook_data, self.context.hook_data['test'])

    def test_run_step_disabled(self):
        hook = Hook("test", path=self.mock_hook_path, enabled=False)

        status = hook.run_step(provider_builder=self.provider_builder,
                               context=self.context)
        self.assertIsInstance(status, NotSubmittedStatus)

    def test_run_step_stack_dep_missing(self):
        hook = Hook("test", path=self.mock_hook_path,
                    args={"hello": "${output undeployed-stack::Output}"})
        stack_fqn = self.context.get_stack("undeployed-stack").fqn

        status = hook.run_step(provider_builder=self.provider_builder,
                               context=self.context)
        self.assertIsInstance(status, SkippedStatus)
        self.assertEqual(status.reason,
                         "required stack not deployed: {}".format(stack_fqn))

    def test_run_step_hook_raised(self):
        hook = Hook("test", path=self.mock_hook_path)
        err = HookExecutionFailed(hook, cause=RuntimeError("canary"))
        hook.run = mock.Mock(side_effect=err)

        status = hook.run_step(provider_builder=self.provider_builder,
                               context=self.context)
        self.assertIsInstance(status, FailedStatus)
        self.assertIn("canary", status.reason)
        self.assertIn("threw exception", status.reason)

    def test_run_step_hook_failed(self):
        hook = Hook("test", path=self.mock_hook_path, required=True)
        hook.run = mock.Mock(return_value=False)

        status = hook.run_step(provider_builder=self.provider_builder,
                               context=self.context)
        self.assertIsInstance(status, SkippedStatus)

    def test_run_step_hook_succeeded(self):
        hook = Hook("test", path=self.mock_hook_path)
        hook.run = mock.Mock(return_value=True)

        status = hook.run_step(provider_builder=self.provider_builder,
                               context=self.context)
        self.assertEqual(status, COMPLETE)
