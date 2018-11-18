from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str

from stacker.session_cache import get_session

from . import LookupHandler
from ...util import read_value_from_path

TYPE_NAME = "ssmstore"


class SsmstoreLookup(LookupHandler):
    @classmethod
    def handle(cls, value, **kwargs):
        """Retrieve (and decrypt if applicable) a parameter from
        AWS SSM Parameter Store.

        ssmstore field types should be in the following format:

            [<region>@]ssmkey

        Note: The region is optional, and defaults to us-east-1 if not given.

        For example:

            # In stacker we would reference the encrypted value like:
            conf_key: ${ssmstore us-east-1@ssmkey}

            You can optionally store the value in a file, ie:

            ssmstore_value.txt
            us-east-1@ssmkey

            and reference it within stacker (NOTE: the path should be relative
            to the stacker config file):

            conf_key: ${ssmstore file://ssmstore_value.txt}

            # Both of the above would resolve to
            conf_key: PASSWORD

        """
        value = read_value_from_path(value)

        region = "us-east-1"
        if "@" in value:
            region, value = value.split("@", 1)

        client = get_session(region).client("ssm")
        response = client.get_parameters(
            Names=[
                value,
            ],
            WithDecryption=True
        )
        if 'Parameters' in response:
            return str(response['Parameters'][0]['Value'])

        raise ValueError('SSMKey "{}" does not exist in region {}'.format(
            value, region))
