# encoding: utf-8

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import mock
import base64
import yaml
import json
from troposphere import Base64, GenericHelperFn, Join

from stacker.lookups.handlers.file import (json_codec, handler,
                                           parameterized_codec, yaml_codec)


def to_template_dict(obj):
    """Extract the CFN template dict of an object for test comparisons"""

    if hasattr(obj, 'to_dict') and callable(obj.to_dict):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return dict((key, to_template_dict(value))
                    for (key, value) in obj.items())
    elif isinstance(obj, (list, tuple)):
        return type(obj)(to_template_dict(item) for item in obj)
    else:
        return obj


class TestFileTranslator(unittest.TestCase):
    @staticmethod
    def assertTemplateEqual(left, right):
        """
        Assert that two codec results are equivalent

        Convert both sides to their template representations, since Troposphere
        objects are not natively comparable
        """
        return to_template_dict(left) == to_template_dict(right)

    def test_parameterized_codec_b64(self):
        expected = Base64(
            Join(u'', [u'Test ', {u'Ref': u'Interpolation'}, u' Here'])
        )

        out = parameterized_codec(u'Test {{Interpolation}} Here', True)
        self.assertEqual(Base64, out.__class__)
        self.assertTemplateEqual(expected, out)

    def test_parameterized_codec_plain(self):
        expected = Join(u'', [u'Test ', {u'Ref': u'Interpolation'}, u' Here'])

        out = parameterized_codec(u'Test {{Interpolation}} Here', False)
        self.assertEqual(GenericHelperFn, out.__class__)
        self.assertTemplateEqual(expected, out)

    def test_parameterized_codec_plain_no_interpolation(self):
        expected = u'Test Without Interpolation Here'

        out = parameterized_codec(u'Test Without Interpolation Here', False)
        self.assertEqual(GenericHelperFn, out.__class__)
        self.assertTemplateEqual(expected, out)

    def test_yaml_codec_raw(self):
        structured = {
            u'Test': [1, None, u'unicode ✓', {u'some': u'obj'}]
        }
        # Note: must use safe_dump, since regular dump adds !python/unicode
        # tags, which we don't want, or we can't be sure we're correctly
        # loading string as unicode.
        raw = yaml.safe_dump(structured)

        out = yaml_codec(raw, parameterized=False)
        self.assertEqual(structured, out)

    def test_yaml_codec_parameterized(self):
        processed = {
            u'Test': Join(u'', [u'Test ', {u'Ref': u'Interpolation'},
                          u' Here'])
        }
        structured = {
            u'Test': u'Test {{Interpolation}} Here'
        }
        raw = yaml.safe_dump(structured)

        out = yaml_codec(raw, parameterized=True)
        self.assertTemplateEqual(processed, out)

    def test_json_codec_raw(self):
        structured = {
            u'Test': [1, None, u'str', {u'some': u'obj'}]
        }
        raw = json.dumps(structured)

        out = json_codec(raw, parameterized=False)
        self.assertEqual(structured, out)

    def test_json_codec_parameterized(self):
        processed = {
            u'Test': Join(u'', [u'Test ', {u'Ref': u'Interpolation'},
                                u' Here'])
        }
        structured = {
            u'Test': u'Test {{Interpolation}} Here'
        }
        raw = json.dumps(structured)

        out = json_codec(raw, parameterized=True)
        self.assertTemplateEqual(processed, out)

    @mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                return_value='')
    def test_file_loaded(self, content_mock):
        handler(u'plain:file://tmp/test')
        content_mock.assert_called_with(u'file://tmp/test')

    @mock.patch('stacker.lookups.handlers.file.read_value_from_path',
                return_value=u'Hello, world')
    def test_handler_plain(self, _):
        out = handler(u'plain:file://tmp/test')
        self.assertEqual(u'Hello, world', out)

    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_b64(self, content_mock):
        plain = u'Hello, world'
        encoded = base64.b64encode(plain.encode('utf8'))

        content_mock.return_value = plain
        out = handler(u'base64:file://tmp/test')
        self.assertEqual(encoded, out)

    @mock.patch('stacker.lookups.handlers.file.parameterized_codec')
    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_parameterized(self, content_mock, codec_mock):
        result = mock.Mock()
        codec_mock.return_value = result

        out = handler(u'parameterized:file://tmp/test')
        codec_mock.assert_called_once_with(content_mock.return_value, False)

        self.assertEqual(result, out)

    @mock.patch('stacker.lookups.handlers.file.parameterized_codec')
    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_parameterized_b64(self, content_mock, codec_mock):
        result = mock.Mock()
        codec_mock.return_value = result

        out = handler(u'parameterized-b64:file://tmp/test')
        codec_mock.assert_called_once_with(content_mock.return_value, True)

        self.assertEqual(result, out)

    @mock.patch('stacker.lookups.handlers.file.yaml_codec')
    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_yaml(self, content_mock, codec_mock):
        result = mock.Mock()
        codec_mock.return_value = result

        out = handler(u'yaml:file://tmp/test')
        codec_mock.assert_called_once_with(content_mock.return_value,
                                           parameterized=False)

        self.assertEqual(result, out)

    @mock.patch('stacker.lookups.handlers.file.yaml_codec')
    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_yaml_parameterized(self, content_mock, codec_mock):
        result = mock.Mock()
        codec_mock.return_value = result

        out = handler(u'yaml-parameterized:file://tmp/test')
        codec_mock.assert_called_once_with(content_mock.return_value,
                                           parameterized=True)

        self.assertEqual(result, out)

    @mock.patch('stacker.lookups.handlers.file.json_codec')
    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_json(self, content_mock, codec_mock):
        result = mock.Mock()
        codec_mock.return_value = result

        out = handler(u'json:file://tmp/test')
        codec_mock.assert_called_once_with(content_mock.return_value,
                                           parameterized=False)

        self.assertEqual(result, out)

    @mock.patch('stacker.lookups.handlers.file.json_codec')
    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_handler_json_parameterized(self, content_mock, codec_mock):
        result = mock.Mock()
        codec_mock.return_value = result

        out = handler(u'json-parameterized:file://tmp/test')
        codec_mock.assert_called_once_with(content_mock.return_value,
                                           parameterized=True)

        self.assertEqual(result, out)

    @mock.patch('stacker.lookups.handlers.file.read_value_from_path')
    def test_unknown_codec(self, _):
        with self.assertRaises(KeyError):
            handler(u'bad:file://tmp/test')
