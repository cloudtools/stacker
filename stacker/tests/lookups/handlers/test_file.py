import unittest
import mock
import base64
import troposphere

from stacker.lookups.handlers.file import parameterized_codec, handler


class TestFileTranslator(unittest.TestCase):
    def test_parameterized_codec_b64(self):
        expected = {
            'Fn::Base64': {
                'Fn::Join': [
                    '',
                    ['Test ', {'Ref': 'Interpolation'}, ' Here']
                ]
            }
        }
        self.assertEqual(
            expected,
            parameterized_codec('Test {{Interpolation}} Here', True).data
        )

    def test_parameterized_codec_plain(self):
        expected = {
            'Fn::Join': ['', ['Test ', {'Ref': 'Interpolation'}, ' Here']]
        }
        self.assertEqual(
            expected,
            parameterized_codec('Test {{Interpolation}} Here', False).data
        )

    def test_file_loaded(self):
        with mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                        return_value='') as amock:
            handler('plain:file://tmp/test')
            amock.assert_called_with('file://tmp/test')

    def test_handler_plain(self):
        expected = 'Hello, world'
        with mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                        return_value=expected):
            out = handler('plain:file://tmp/test')
            self.assertEqual(expected, out)

    def test_handler_b64(self):
        expected = 'Hello, world'
        with mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                        return_value=expected):
            out = handler('base64:file://tmp/test')
            self.assertEqual(expected, base64.b64decode(out))

    def test_handler_parameterized(self):
        expected = 'Hello, world'
        with mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                        return_value=expected):
            out = handler('parameterized:file://tmp/test')
            self.assertEqual(troposphere.GenericHelperFn, type(out))

    def test_handler_parameterized_b64(self):
        expected = 'Hello, world'
        with mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                        return_value=expected):
            out = handler('parameterized-b64:file://tmp/test')
            self.assertEqual(troposphere.Base64, type(out))

    def test_unknown_codec(self):
        expected = 'Hello, world'
        with mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                        return_value=expected):
            with self.assertRaises(KeyError):
                handler('bad:file://tmp/test')
