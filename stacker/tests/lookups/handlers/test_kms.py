import base64
from mock import patch
import unittest

from stacker.lookups.handlers.kms import handler


class TestKMSHandler(unittest.TestCase):

    def setUp(self):
        patcher = patch("botocore.session")
        self.addCleanup(patcher.stop)
        self.session = patcher.start()
        self.kms = self.session.get_session().create_client()
        self.input = base64.b64encode("encrypted test value")
        self.value = {"Plaintext": "test value"}

    def test_kms_handler(self):
        self.kms.decrypt.return_value = self.value
        decrypted = handler(self.input)
        self.assertEqual(decrypted, self.value["Plaintext"])

    def test_kms_handler_with_region(self):
        handler("us-west-2@{}".format(self.input))
        self.assertEqual(self.kms.decrypt.call_args[1]["CiphertextBlob"],
                         "encrypted test value")
        kwargs = self.session.get_session().create_client.call_args[1]
        self.assertEqual(kwargs["region_name"], "us-west-2")
