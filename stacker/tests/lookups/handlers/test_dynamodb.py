from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
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
        self.get_parameters_response = {'Item': {'TestMap': {'M': {
            'String1': {'S': 'StringVal1'},
            'List1': {'L': [
                {'S': 'ListVal1'},
                {'S': 'ListVal2'}]},
            'Number1': {'N': '12345'}, }}}}

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_handler(self, mock_client):
        expected_params = {
            'TableName': 'TestTable',
            'Key': {
                'TestKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,String1'
        }
        base_lookup_key = 'TestTable@TestKey:TestVal.TestMap[M].String1'
        base_lookup_key_valid = 'StringVal1'
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  expected_params)
        with self.stubber:
            value = handler(base_lookup_key)
            self.assertEqual(value, base_lookup_key_valid)

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_number_handler(self, mock_client):
        expected_params = {
            'TableName': 'TestTable',
            'Key': {
                'TestKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,Number1'
        }
        base_lookup_key = 'TestTable@TestKey:TestVal.' \
            'TestMap[M].Number1[N]'
        base_lookup_key_valid = 12345
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  expected_params)
        with self.stubber:
            value = handler(base_lookup_key)
            self.assertEqual(value, base_lookup_key_valid)

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_list_handler(self, mock_client):
        expected_params = {
            'TableName': 'TestTable',
            'Key': {
                'TestKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,List1'
        }
        base_lookup_key = 'TestTable@TestKey:TestVal.' \
            'TestMap[M].List1[L]'
        base_lookup_key_valid = ['ListVal1', 'ListVal2']
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  expected_params)
        with self.stubber:
            value = handler(base_lookup_key)
            self.assertEqual(value, base_lookup_key_valid)

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_empty_table_handler(self, mock_client):
        expected_params = {
            'TableName': '',
            'Key': {
                'TestKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,String1'
        }
        base_lookup_key = '@TestKey:TestVal.TestMap[M].String1'
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  expected_params)
        with self.stubber:
            try:
                handler(base_lookup_key)
            except ValueError as e:
                self.assertEqual(
                    'Please make sure to include a dynamodb table name',
                    str(e))

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_missing_table_handler(self, mock_client):
        expected_params = {
            'Key': {
                'TestKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,String1'
        }
        base_lookup_key = 'TestKey:TestVal.TestMap[M].String1'
        self.stubber.add_response('get_item',
                                  self.get_parameters_response,
                                  expected_params)
        with self.stubber:
            try:
                handler(base_lookup_key)
            except ValueError as e:
                self.assertEqual(
                    'Please make sure to include a tablename',
                    str(e))

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_invalid_table_handler(self, mock_client):
        expected_params = {
            'TableName': 'FakeTable',
            'Key': {
                'TestKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,String1'
        }
        base_lookup_key = 'FakeTable@TestKey:TestVal.TestMap[M].String1'
        service_error_code = 'ResourceNotFoundException'
        self.stubber.add_client_error('get_item',
                                      service_error_code=service_error_code,
                                      expected_params=expected_params)
        with self.stubber:
            try:
                handler(base_lookup_key)
            except ValueError as e:
                self.assertEqual(
                    'Cannot find the dynamodb table: FakeTable',
                    str(e))

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_invalid_partition_key_handler(self, mock_client):
        expected_params = {
            'TableName': 'TestTable',
            'Key': {
                'FakeKey': {'S': 'TestVal'}
            },
            'ProjectionExpression': 'TestVal,TestMap,String1'
        }
        base_lookup_key = 'TestTable@FakeKey:TestVal.TestMap[M].String1'
        service_error_code = 'ValidationException'
        self.stubber.add_client_error('get_item',
                                      service_error_code=service_error_code,
                                      expected_params=expected_params)

        with self.stubber:
            try:
                handler(base_lookup_key)
            except ValueError as e:
                self.assertEqual(
                    'No dynamodb record matched the partition key: FakeKey',
                    str(e))

    @mock.patch('stacker.lookups.handlers.dynamodb.get_session',
                return_value=SessionStub(client))
    def test_dynamodb_invalid_partition_val_handler(self, mock_client):
        expected_params = {
            'TableName': 'TestTable',
            'Key': {
                'TestKey': {'S': 'FakeVal'}
            },
            'ProjectionExpression': 'FakeVal,TestMap,String1'
        }
        empty_response = {'ResponseMetadata': {}}
        base_lookup_key = 'TestTable@TestKey:FakeVal.TestMap[M].String1'
        self.stubber.add_response('get_item',
                                  empty_response,
                                  expected_params)
        with self.stubber:
            try:
                handler(base_lookup_key)
            except ValueError as e:
                self.assertEqual(
                    'The dynamodb record could not be found using '
                    'the following key: {\'S\': \'FakeVal\'}',
                    str(e))
