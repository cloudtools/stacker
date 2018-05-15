import unittest
import mock
from botocore.stub import Stubber
from stacker.lookups.handlers.ssmstore import handler
import boto3
from stacker.tests.factories import SessionStub


class TestSSMStoreHandler(unittest.TestCase):
    client = boto3.client('ssm', region_name='us-east-1')
    au_client = boto3.client('ssm', region_name='ap-southeast-2')

    def setUp(self):
        self.stubber = Stubber(self.client)
        self.au_stubber = Stubber(self.au_client)
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
        self.au_get_parameters_response = {
            'Parameters': [
                {
                    'Name': 'ssmkey',
                    'Type': 'String',
                    'Value': 'au_ssmvalue'
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
        self.au_ssmvalue = "au_ssmvalue"

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
                return_value=SessionStub(au_client))
    def test_ssmstore_handler_with_implicit_region(self, mock_client):
        self.au_stubber.add_response(
            'get_parameters',
            self.au_get_parameters_response,
            self.expected_params,
        )
        with self.au_stubber:
            value = handler(self.ssmkey)
            self.assertEqual(value, self.au_ssmvalue)

    @mock.patch('stacker.lookups.handlers.ssmstore.get_session',
                return_value=SessionStub(au_client))
    def test_ssmstore_handler_with_explicit_region(self, mock_client):
        self.au_stubber.add_response(
            'get_parameters',
            self.au_get_parameters_response,
            self.expected_params,
        )
        region = "ap-southeast-2"
        temp_value = "{}@{}".format(region, self.ssmkey)
        with self.au_stubber:
            value = handler(temp_value)
            self.assertEqual(value, self.au_ssmvalue)
