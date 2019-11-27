from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import codecs
from mock import patch
import unittest

import boto3
from botocore.stub import Stubber

from stacker.lookups.handlers.kms import KmsLookup
from stacker.tests.factories import SessionStub, mock_provider


REGION = 'us-east-1'


class TestKMSHandler(unittest.TestCase):
    client = boto3.client('kms', region_name=REGION)

    def setUp(self):
        self.stubber = Stubber(self.client)
        self.provider = mock_provider(region=REGION)
        self.secret = b'my secret'

    @patch("stacker.lookups.handlers.kms.get_session",
           return_value=SessionStub(client))
    def test_kms_handler(self, _mock_client):
        self.stubber.add_response('decrypt', {'Plaintext': self.secret},
                                  {'CiphertextBlob': codecs.decode(self.secret,
                                                                   'base64')})

        with self.stubber:
            self.assertEqual(self.secret,
                             KmsLookup.handle(value=self.secret.decode(),
                                              provider=self.provider))
            self.stubber.assert_no_pending_responses()

    @patch("stacker.lookups.handlers.kms.get_session",
           return_value=SessionStub(client))
    def test_kms_handler_with_region(self, _mock_client):
        value = '{}@{}'.format(REGION, self.secret.decode())

        self.stubber.add_response('decrypt', {'Plaintext': self.secret},
                                  {'CiphertextBlob': codecs.decode(self.secret,
                                                                   'base64')})

        with self.stubber:
            self.assertEqual(self.secret,
                             KmsLookup.handle(value=value,
                                              provider=self.provider))
            self.stubber.assert_no_pending_responses()
