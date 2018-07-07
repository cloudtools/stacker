from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os

from ...util import read_value_from_path

TYPE_NAME = "envvar"


def handler(value, **kwargs):
    """Retrieve an environment variable.

    For example:

        # In stacker we would reference the environment variable like this:
        conf_key: ${envvar ENV_VAR_NAME}

        You can optionally store the value in a file, ie:

        $ cat envvar_value.txt
        ENV_VAR_NAME

        and reference it within stacker (NOTE: the path should be relative to
        the stacker config file):

        conf_key: ${envvar file://envvar_value.txt}

        # Both of the above would resolve to
        conf_key: ENV_VALUE
    """
    value = read_value_from_path(value)

    try:
        return os.environ[value]
    except KeyError:
        raise ValueError('EnvVar "{}" does not exist'.format(value))
