from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import codecs
from stacker.session_cache import get_session

from . import LookupHandler
from ...util import read_value_from_path

TYPE_NAME = "kms"


class KmsLookup(LookupHandler):
    @classmethod
    def handle(cls, value, **kwargs):
        """Decrypt the specified value with a master key in KMS.

        kmssimple field types should be in the following format:

            [<region>@]<base64 encrypted value>

        Note: The region is optional, and defaults to the environment's
        `AWS_DEFAULT_REGION` if not specified.

        For example:

            # We use the aws cli to get the encrypted value for the string
            # "PASSWORD" using the master key called "myStackerKey" in
            # us-east-1
            $ aws --region us-east-1 kms encrypt --key-id alias/myStackerKey \
                    --plaintext "PASSWORD" --output text --query CiphertextBlob

            CiD6bC8t2Y<...encrypted blob...>

            # In stacker we would reference the encrypted value like:
            conf_key: ${kms us-east-1@CiD6bC8t2Y<...encrypted blob...>}

            You can optionally store the encrypted value in a file, ie:

            kms_value.txt
            us-east-1@CiD6bC8t2Y<...encrypted blob...>

            and reference it within stacker (NOTE: the path should be relative
            to the stacker config file):

            conf_key: ${kms file://kms_value.txt}

            # Both of the above would resolve to
            conf_key: PASSWORD

        """
        value = read_value_from_path(value)

        region = None
        if "@" in value:
            region, value = value.split("@", 1)

        kms = get_session(region).client('kms')

        # encode str value as an utf-8 bytestring for use with codecs.decode.
        value = value.encode('utf-8')

        # get raw but still encrypted value from base64 version.
        decoded = codecs.decode(value, 'base64')

        # decrypt and return the plain text raw value.
        return kms.decrypt(CiphertextBlob=decoded)["Plaintext"]
