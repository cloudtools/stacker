from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import codecs
import unittest

from moto import mock_kms

from stacker.lookups.handlers.kms import KmsLookup
from ...factories import mock_boto3_client, mock_context, mock_provider

REGION = 'us-east-1'


class TestKMSHandler(unittest.TestCase):
    def setUp(self):
        self.context = mock_context()
        self.provider = mock_provider(region=REGION)

        self.mock_kms = mock_kms()
        self.mock_kms.start()
        self.kms, self.client_mock = mock_boto3_client('kms', region=REGION)
        self.client_mock.start()

        self.plain = b"my secret"
        self.secret = self.kms.encrypt(
            KeyId="alias/stacker",
            Plaintext=codecs.encode(self.plain, 'base64').decode('utf-8'),
        )["CiphertextBlob"]
        if isinstance(self.secret, bytes):
            self.secret = self.secret.decode()

    def tearDown(self):
        self.client_mock.stop()
        self.mock_kms.stop()

    def test_kms_handler(self):
        decrypted = KmsLookup.handle(self.secret, self.context, self.provider)
        self.assertEqual(decrypted, self.plain)

    def test_kms_handler_with_region(self):
        value = "%s@%s" % (REGION, self.secret)
        decrypted = KmsLookup.handle(value, self.context, self.provider)
        self.assertEqual(decrypted, self.plain)
