from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import unittest
from subprocess import PIPE

import mock

from stacker.context import Context
from stacker.config import Config
from stacker.hooks.command import run_command

from ..factories import mock_provider


class MockProcess(object):
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = None

    def communicate(self, stdin):
        self.stdin = stdin
        return (self.stdout, self.stderr)

    def wait(self):
        return self.returncode

    def kill(self):
        return


class TestCommandHook(unittest.TestCase):
    def setUp(self):
        self.context = Context(
            config=Config({'namespace': 'test', 'stacker_bucket': 'test'}))
        self.provider = mock_provider(region="us-east-1")

        self.mock_process = MockProcess()
        self.popen_mock = \
            mock.patch('stacker.hooks.command.Popen',
                       return_value=self.mock_process).start()

        self.devnull = mock.Mock()
        self.devnull_mock = \
            mock.patch('stacker.hooks.command._devnull',
                       return_value=self.devnull).start()

    def tearDown(self):
        self.devnull_mock.stop()
        self.popen_mock.stop()

    def run_hook(self, **kwargs):
        real_kwargs = {
            'context': self.context,
            'provider': self.provider,
        }
        real_kwargs.update(kwargs)

        return run_command(**real_kwargs)

    def test_command_ok(self):
        self.mock_process.returncode = 0
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        results = self.run_hook(command=['foo'])

        self.assertEqual(
            results, {'returncode': 0, 'stdout': None, 'stderr': None})
        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=self.devnull, stdout=None, stderr=None, env=None)

    def test_command_fail(self):
        self.mock_process.returncode = 1
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        results = self.run_hook(command=['foo'])

        self.assertEqual(results, None)
        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=self.devnull, stdout=None, stderr=None, env=None)

    def test_command_ignore_status(self):
        self.mock_process.returncode = 1
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        results = self.run_hook(command=['foo'], ignore_status=True)

        self.assertEqual(
            results, {'returncode': 1, 'stdout': None, 'stderr': None})
        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=self.devnull, stdout=None, stderr=None, env=None)

    def test_command_quiet(self):
        self.mock_process.returncode = 0
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        results = self.run_hook(command=['foo'], quiet=True)
        self.assertEqual(
            results, {'returncode': 0, 'stdout': None, 'stderr': None})

        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=self.devnull, stdout=self.devnull,
            stderr=self.devnull, env=None)

    def test_command_interactive(self):
        self.mock_process.returncode = 0
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        results = self.run_hook(command=['foo'], interactive=True)
        self.assertEqual(
            results, {'returncode': 0, 'stdout': None, 'stderr': None})

        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=None, stdout=None, stderr=None, env=None)

    def test_command_input(self):
        self.mock_process.returncode = 0
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        results = self.run_hook(command=['foo'], stdin='hello world')
        self.assertEqual(
            results, {'returncode': 0, 'stdout': None, 'stderr': None})

        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=PIPE, stdout=None, stderr=None, env=None)
        self.assertEqual(self.mock_process.stdin, 'hello world')

    def test_command_capture(self):
        self.mock_process.returncode = 0
        self.mock_process.stdout = 'hello'
        self.mock_process.stderr = 'world'

        results = self.run_hook(command=['foo'], capture=True)
        self.assertEqual(
            results, {'returncode': 0, 'stdout': 'hello', 'stderr': 'world'})

        self.popen_mock.assert_called_once_with(
            ['foo'], stdin=self.devnull, stdout=PIPE, stderr=PIPE, env=None)

    def test_command_env(self):
        self.mock_process.returncode = 0
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        with mock.patch.dict(os.environ, {'foo': 'bar'}, clear=True):
            results = self.run_hook(command=['foo'], env={'hello': 'world'})

            self.assertEqual(results, {'returncode': 0,
                                       'stdout': None,
                                       'stderr': None})
            self.popen_mock.assert_called_once_with(
                ['foo'], stdin=self.devnull, stdout=None, stderr=None,
                env={'hello': 'world', 'foo': 'bar'})
