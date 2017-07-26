import re
import base64

from ...util import read_value_from_path
from troposphere import GenericHelperFn, Base64

TYPE_NAME = "file"


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


def parameterized_codec(raw, b64):
    pattern = re.compile(r'{{([::|\w]+)}}')

    parts = []
    s_index = 0

    for match in pattern.finditer(raw):
        parts.append(raw[s_index:match.start()])
        parts.append({"Ref": match.group(1)})
        s_index = match.end()

    parts.append(raw[s_index:])
    result = {"Fn::Join": ["", parts]}

    # Note, since we want a raw JSON object (not a string) output in the
    # template, we wrap the result in GenericHelperFn (not needed if we're
    # using Base64)
    return Base64(result) if b64 else GenericHelperFn(result)


CODECS = {
    "plain": lambda x: x,
    "base64": base64.b64encode,
    "parameterized": lambda x: parameterized_codec(x, False),
    "parameterized-b64": lambda x: parameterized_codec(x, True)
}
