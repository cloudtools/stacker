from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from botocore.stub import Stubber

from stacker.lookups.handlers.dynamodb import DynamodbLookup
from ...factories import mock_context, mock_provider, mock_boto3_client

REGION = 'us-east-1'


class TestDynamoDBHandler(unittest.TestCase):
    def setUp(self):
        self.context = mock_context()
        self.provider = mock_provider(region=REGION)

        self.dynamodb, self.client_mock = \
            mock_boto3_client("dynamodb", region=REGION)
        self.client_mock.start()
        self.stubber = Stubber(self.dynamodb)
        self.stubber.activate()

        self.get_parameters_response = {'Item': {'TestMap': {'M': {
            'String1': {'S': 'StringVal1'},
            'List1': {'L': [
                {'S': 'ListVal1'},
                {'S': 'ListVal2'}]},
            'Number1': {'N': '12345'}, }}}}

    def tearDown(self):
        self.client_mock.stop()
        self.stubber.deactivate()

    def test_dynamodb_handler(self):
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
        value = DynamodbLookup.handle(
            base_lookup_key, self.context, self.provider)
        self.assertEqual(value, base_lookup_key_valid)

    def test_dynamodb_number_handler(self):
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

        value = DynamodbLookup.handle(
            base_lookup_key, self.context, self.provider)
        self.assertEqual(value, base_lookup_key_valid)

    def test_dynamodb_list_handler(self):
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

        value = DynamodbLookup.handle(
            base_lookup_key, self.context, self.provider)
        self.assertEqual(value, base_lookup_key_valid)

    def test_dynamodb_empty_table_handler(self):
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

        msg = 'Please make sure to include a dynamodb table name'
        with self.assertRaises(ValueError) as raised:
            DynamodbLookup.handle(
                base_lookup_key, self.context, self.provider)
            self.assertEquals(raised.exception.message, msg)

    def test_dynamodb_missing_table_handler(self):
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

        msg = 'Please make sure to include a tablename'
        with self.assertRaises(ValueError) as raised:
            DynamodbLookup.handle(
                base_lookup_key, self.context, self.provider)
            self.assertEquals(raised.exception.message, msg)

    def test_dynamodb_invalid_table_handler(self):
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

        msg = 'Cannot find the dynamodb table: FakeTable'
        with self.assertRaises(ValueError) as raised:
            DynamodbLookup.handle(
                base_lookup_key, self.context, self.provider)
            self.assertEquals(raised.exception.message, msg)

    def test_dynamodb_invalid_partition_key_handler(self):
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

        msg = 'No dynamodb record matched the partition key: FakeKey'
        with self.assertRaises(ValueError) as raised:
            DynamodbLookup.handle(
                base_lookup_key, self.context, self.provider)
            self.assertEquals(raised.exception.message, msg)

    def test_dynamodb_invalid_partition_val_handler(self):
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

        msg = ('The dynamodb record could not be found using the following '
               'key: {\'S\': \'FakeVal\'}')
        with self.assertRaises(ValueError) as raised:
            DynamodbLookup.handle(
                base_lookup_key, self.context, self.provider)
            self.assertEquals(raised.exception.message, msg)
