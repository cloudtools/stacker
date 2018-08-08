from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import bytes, str

import base64
import json
import re
try:
    from collections.abc import Mapping, Sequence
except ImportError:
    from collections import Mapping, Sequence

import yaml

from troposphere import GenericHelperFn, Base64

from ...util import read_value_from_path


TYPE_NAME = "file"

_PARAMETER_PATTERN = re.compile(r'{{([::|\w]+)}}')


def handler(value, **kwargs):
    """Translate a filename into the file contents.

    Fields should use the following format::

        <codec>:<path>

    For example::

        # We've written a file to /some/path:
        $ echo "hello there" > /some/path

        # In stacker we would reference the contents of this file with the
        # following
        conf_key: ${file plain:file://some/path}

        # The above would resolve to
        conf_key: hello there

        # Or, if we used wanted a base64 encoded copy of the file data
        conf_key: ${file base64:file://some/path}

        # The above would resolve to
        conf_key: aGVsbG8gdGhlcmUK

    Supported codecs:

        - plain

        - base64 - encode the plain text file at the given path with base64
          prior to returning it

        - parameterized - the same as plain, but additionally supports
          referencing template parameters to create userdata that's
          supplemented with information from the template, as is commonly
          needed in EC2 UserData. For example, given a template parameter of
          BucketName, the file could contain the following text::

            #!/bin/sh
            aws s3 sync s3://{{BucketName}}/somepath /somepath

          and then you could use something like this in the YAML config file::

            UserData: ${file parameterized:/path/to/file}

          resulting in the UserData parameter being defined as::

              { "Fn::Join" : ["", [
                  "#!/bin/sh\\naws s3 sync s3://",
                  {"Ref" : "BucketName"},
                  "/somepath /somepath"
              ]] }

        - parameterized-b64 - the same as parameterized, with the results
          additionally wrapped in *{ "Fn::Base64": ... }* , which is what you
          actually need for EC2 UserData

    When using parameterized-b64 for UserData, you should use a variable
    defined as such:

    .. code-block:: python

        from troposphere import AWSHelperFn

          "UserData": {
              "type": AWSHelperFn,
              "description": "Instance user data",
              "default": Ref("AWS::NoValue")
          }

    and then assign UserData in a LaunchConfiguration or Instance to
    *self.get_variables()["UserData"]*. Note that we use AWSHelperFn as the
    type because the parameterized-b64 codec returns either a Base64 or a
    GenericHelperFn troposphere object
    """

    try:
        codec, path = value.split(":", 1)
    except ValueError:
        raise TypeError(
            "File value must be of the format"
            " \"<codec>:<path>\" (got %s)" % (value)
        )

    value = read_value_from_path(path)

    return CODECS[codec](value)


def _parameterize_string(raw):
    """Substitute placeholders in a string using CloudFormation references

    Args:
        raw (`str`): String to be processed. Byte strings are not
        supported; decode them before passing them to this function.

    Returns:
        `str` | :class:`troposphere.GenericHelperFn`: An expression with
            placeholders from the input replaced, suitable to be passed to
            Troposphere to be included in CloudFormation template. This will
            be the input string without modification if no substitutions are
            found, and a composition of CloudFormation calls otherwise.
    """

    parts = []
    s_index = 0

    for match in _PARAMETER_PATTERN.finditer(raw):
        parts.append(raw[s_index:match.start()])
        parts.append({u"Ref": match.group(1)})
        s_index = match.end()

    if not parts:
        return GenericHelperFn(raw)

    parts.append(raw[s_index:])
    return GenericHelperFn({u"Fn::Join": [u"", parts]})


def parameterized_codec(raw, b64):
    """Parameterize a string, possibly encoding it as Base64 afterwards

    Args:
        raw (`str` | `bytes`): String to be processed. Byte strings will be
            interpreted as UTF-8.
        b64 (`bool`): Whether to wrap the output in a Base64 CloudFormation
            call

    Returns:
        :class:`troposphere.AWSHelperFn`: output to be included in a
        CloudFormation template.
    """

    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')

    result = _parameterize_string(raw)

    # Note, since we want a raw JSON object (not a string) output in the
    # template, we wrap the result in GenericHelperFn (not needed if we're
    # using Base64)
    return Base64(result.data) if b64 else result


def _parameterize_obj(obj):
    """Recursively parameterize all strings contained in an object.

    Parameterizes all values of a Mapping, all items of a Sequence, an
    unicode string, or pass other objects through unmodified.

    Byte strings will be interpreted as UTF-8.

    Args:
        obj: data to parameterize

    Return:
        A parameterized object to be included in a CloudFormation template.
        Mappings are converted to `dict`, Sequences are converted to  `list`,
        and strings possibly replaced by compositions of function calls.
    """

    if isinstance(obj, Mapping):
        return dict((key, _parameterize_obj(value))
                    for key, value in obj.items())
    elif isinstance(obj, bytes):
        return _parameterize_string(obj.decode('utf8'))
    elif isinstance(obj, str):
        return _parameterize_string(obj)
    elif isinstance(obj, Sequence):
        return list(_parameterize_obj(item) for item in obj)
    else:
        return obj


class SafeUnicodeLoader(yaml.SafeLoader):
    def construct_yaml_str(self, node):
        return self.construct_scalar(node)


def yaml_codec(raw, parameterized=False):
    data = yaml.load(raw, Loader=SafeUnicodeLoader)
    return _parameterize_obj(data) if parameterized else data


def json_codec(raw, parameterized=False):
    data = json.loads(raw)
    return _parameterize_obj(data) if parameterized else data


CODECS = {
    "plain": lambda x: x,
    "base64": lambda x: base64.b64encode(x.encode('utf8')),
    "parameterized": lambda x: parameterized_codec(x, False),
    "parameterized-b64": lambda x: parameterized_codec(x, True),
    "yaml": lambda x: yaml_codec(x, parameterized=False),
    "yaml-parameterized": lambda x: yaml_codec(x, parameterized=True),
    "json": lambda x: json_codec(x, parameterized=False),
    "json-parameterized": lambda x: json_codec(x, parameterized=True),
}
