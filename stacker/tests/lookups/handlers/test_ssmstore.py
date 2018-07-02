from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
import mock
from botocore.stub import Stubber
from stacker.lookups.handlers.ssmstore import handler
import boto3
from stacker.tests.factories import SessionStub


class TestSSMStoreHandler(unittest.TestCase):
    client = boto3.client('ssm', region_name='us-east-1')

    def setUp(self):
        self.stubber = Stubber(self.client)
        self.get_parameters_response = {
            'Parameters': [
                {
                    'Name': 'ssmkey',
                    'Type': 'String',
                    'Value': 'ssmvalue'
                }
            ],
            'InvalidParameters': [
                'invalidssmparam'
            ]
        }
        self.invalid_get_parameters_response = {
            'InvalidParameters': [
                'ssmkey'
            ]
        }
        self.expected_params = {
            'Names': ['ssmkey'],
            'WithDecryption': True
        }
        self.ssmkey = "ssmkey"
        self.ssmvalue = "ssmvalue"

    @mock.patch('stacker.lookups.handlers.ssmstore.get_session',
                return_value=SessionStub(client))
    def test_ssmstore_handler(self, mock_client):
        self.stubber.add_response('get_parameters',
                                  self.get_parameters_response,
                                  self.expected_params)
        with self.stubber:
            value = handler(self.ssmkey)
            self.assertEqual(value, self.ssmvalue)

    @mock.patch('stacker.lookups.handlers.ssmstore.get_session',
                return_value=SessionStub(client))
    def test_ssmstore_invalid_value_handler(self, mock_client):
        self.stubber.add_response('get_parameters',
                                  self.invalid_get_parameters_response,
                                  self.expected_params)
        with self.stubber:
            try:
                handler(self.ssmkey)
            except ValueError:
                assert True

    @mock.patch('stacker.lookups.handlers.ssmstore.get_session',
                return_value=SessionStub(client))
    def test_ssmstore_handler_with_region(self, mock_client):
        self.stubber.add_response('get_parameters',
                                  self.get_parameters_response,
                                  self.expected_params)
        region = "us-east-1"
        temp_value = "%s@%s" % (region, self.ssmkey)
        with self.stubber:
            value = handler(temp_value)
            self.assertEqual(value, self.ssmvalue)
