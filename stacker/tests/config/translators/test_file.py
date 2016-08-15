import unittest
import mock
import base64
import troposphere

from stacker.config.translators.file import parameterized_codec, get_file_value


class TestFileTranslator(unittest.TestCase):
    def setUp(self):
        pass

    def test_parameterized_codec_b64(self):
        expected = {'Fn::Base64': {'Fn::Join': ['', ['Test ', {'Ref': 'Interpolation'}, ' Here']]}}
        self.assertEqual(expected, parameterized_codec('Test {{Interpolation}} Here', True).data)

    def test_parameterized_codec_plain(self):
        expected = {'Fn::Join': ['', ['Test ', {'Ref': 'Interpolation'}, ' Here']]}
        self.assertEqual(expected, parameterized_codec('Test {{Interpolation}} Here', False).data)

    def test_file_loaded(self):
        with mock.patch('stacker.config.translators.file.read_value_from_path', return_value='') as amock:
            get_file_value('plain:file://tmp/test')
            amock.assert_called_with('file://tmp/test')

    def test_get_file_value_plain(self):
        expected = 'Hello, world'
        with mock.patch('stacker.config.translators.file.read_value_from_path', return_value=expected):
            out = get_file_value('plain:file://tmp/test')
            self.assertEqual(expected, out)

    def test_get_file_value_b64(self):
        expected = 'Hello, world'
        with mock.patch('stacker.config.translators.file.read_value_from_path', return_value=expected):
            out = get_file_value('base64:file://tmp/test')
            self.assertEqual(expected, base64.b64decode(out))

    def test_get_file_value_parameterized(self):
        expected = 'Hello, world'
        with mock.patch('stacker.config.translators.file.read_value_from_path', return_value=expected):
            out = get_file_value('parameterized:file://tmp/test')
            self.assertEqual(troposphere.GenericHelperFn, type(out))

    def test_get_file_value_parameterized_b64(self):
        expected = 'Hello, world'
        with mock.patch('stacker.config.translators.file.read_value_from_path', return_value=expected):
            out = get_file_value('parameterized-b64:file://tmp/test')
            self.assertEqual(troposphere.Base64, type(out))

    def test_unknown_codec(self):
        expected = 'Hello, world'
        with mock.patch('stacker.config.translators.file.read_value_from_path', return_value=expected):
            with self.assertRaises(KeyError):
                get_file_value('bad:file://tmp/test')
