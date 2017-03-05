import unittest

from moto import mock_kms

import boto3

from stacker.lookups.handlers.kms import handler


class TestKMSHandler(unittest.TestCase):
    def setUp(self):
        self.plain = "my secret"
        with mock_kms():
            kms = boto3.client("kms", region_name="us-east-1")
            self.secret = kms.encrypt(
                KeyId="alias/stacker",
                Plaintext=self.plain.encode("base64")
            )["CiphertextBlob"]

    def test_kms_handler(self):
        with mock_kms():
            decrypted = handler(self.secret)
            print "DECRYPTED: %s" % decrypted
            self.assertEqual(decrypted, self.plain)

    def test_kms_handler_with_region(self):
        region = "us-east-1"
        value = "%s@%s" % (region, self.secret)
        with mock_kms():
            decrypted = handler(value)
            self.assertEqual(decrypted, self.plain)
