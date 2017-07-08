import unittest
import mock
from botocore.stub import Stubber
from stacker.lookups.handlers.dynamodb import handler
import boto3
from stacker.tests.factories import SessionStub


class TestDynamoDBHandler(unittest.TestCase):
    client = boto3.client('dynamodb', region_name='us-east-1')

    def setUp(self):
        self.stubber = Stubber(self.client)
        self.get_parameters_response = {'Item':
                                        {'TestMap':
                                         {'M':
                                          {
                                              'String1': {'S': 'StringVal1'},
                                              'List1': {'L':
                                                        [
                                                            {'S': 'ListVal1'},
                                                            {'S': 'ListVal2'}
                                                        ]
                                                        },
                                              'Number1': {'N': '12345'},
                                          }
                                          }
                                         }
                                        }

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_handler(self, mock_client):
        self.expected_params = {
            'TableName': "TestTable",
            'Key': {
                "TestKey": {'S': 'TestVal'}
            },
            'ProjectionExpression': "TestVal,TestMap,String1"
        }
        self.base_lookup_key = "TestTable@TestKey:TestVal.TestMap[M].String1"
        self.base_lookup_key_valid = "StringVal1"
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  self.expected_params)
        with self.stubber:
            value = handler(self.base_lookup_key)
            self.assertEqual(value, self.base_lookup_key_valid)

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_number_handler(self, mock_client):
        self.expected_params = {
            'TableName': "TestTable",
            'Key': {
                "TestKey": {'S': 'TestVal'}
            },
            'ProjectionExpression': "TestVal,TestMap,Number1"
        }
        self.base_lookup_key = "TestTable@TestKey:TestVal." \
                               "TestMap[M].Number1[N]"
        self.base_lookup_key_valid = 12345
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  self.expected_params)
        with self.stubber:
            value = handler(self.base_lookup_key)
            self.assertEqual(value, self.base_lookup_key_valid)

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_list_handler(self, mock_client):
        self.expected_params = {
            'TableName': "TestTable",
            'Key': {
                "TestKey": {'S': 'TestVal'}
            },
            'ProjectionExpression': "TestVal,TestMap,List1"
        }
        self.base_lookup_key = "TestTable@TestKey:TestVal." \
                               "TestMap[M].List1[L]"
        self.base_lookup_key_valid = ["ListVal1", "ListVal2"]
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  self.expected_params)
        with self.stubber:
            value = handler(self.base_lookup_key)
            self.assertEqual(value, self.base_lookup_key_valid)
