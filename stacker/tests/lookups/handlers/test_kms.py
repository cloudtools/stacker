from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import codecs
import unittest

from moto import mock_kms

import boto3

from stacker.lookups.handlers.kms import handler


class TestKMSHandler(unittest.TestCase):
    def setUp(self):
        self.plain = b"my secret"
        with mock_kms():
            kms = boto3.client("kms", region_name="us-east-1")
            self.secret = kms.encrypt(
                KeyId="alias/stacker",
                Plaintext=codecs.encode(self.plain, 'base64').decode('utf-8'),
            )["CiphertextBlob"]
            if isinstance(self.secret, bytes):
                self.secret = self.secret.decode()

    def test_kms_handler(self):
        with mock_kms():
            decrypted = handler(self.secret)
            self.assertEqual(decrypted, self.plain)

    def test_kms_handler_with_region(self):
        region = "us-east-1"
        value = "%s@%s" % (region, self.secret)
        with mock_kms():
            decrypted = handler(value)
            self.assertEqual(decrypted, self.plain)
