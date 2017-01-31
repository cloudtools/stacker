import unittest
import boto3
from mock import patch
from botocore.stub import Stubber
from stacker.lookups.handlers.ssmstore import handler


class TestSSMStoreHandler(unittest.TestCase):
    client = boto3.client('ssm')

    def setUp(self):
        self.stubber = Stubber(self.client)
        get_parameters_response = {
            'Parameters': [
                {
                    'Name': 'ssmkey',
                    'Type': 'String',
                    'Value': 'ssmvalue'
                }
            ],
            'InvalidParameters': [
                'invalidparam'
            ]
        }
        expected_params = {
            'Names': ['ssmkey'],
            'WithDecryption': True
        }
        self.stubber.add_response('get_parameters',
                                  get_parameters_response, expected_params)

        self.ssmkey = "ssmkey"
        self.ssmvalue = 'ssmvalue'

    @patch('stacker.lookups.handlers.ssmstore.boto3.client',
           return_value=client)
    def test_ssmstore_handler(self, mock_client):
        with self.stubber:
            value = handler(self.ssmkey)
            print "Value: %s" % value
            self.assertEqual(value, self.ssmvalue)

    @patch('stacker.lookups.handlers.ssmstore.boto3.client',
           return_value=client)
    def test_ssmstore_handler_with_region(self, mock_client):
        region = "us-east-1"
        temp_value = "%s@%s" % (region, self.ssmkey)
        print temp_value
        with self.stubber:
            value = handler(temp_value)
            self.assertEqual(value, self.ssmvalue)
