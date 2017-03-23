import unittest
from mock import (
    MagicMock,
    patch
)
import boto3
from botocore.stub import Stubber
from stacker import exceptions
from datetime import datetime
import json
import botocore


from stacker.providers.aws.default import (
    Message,
    CloudListener,
    Provider,
    parse_message,
    retry_on_throttling
)

from stacker.status import (
    SubmittedStatus,
    CompleteStatus,
)


def create_fake_message_data(stack_name, status, message_id=None):

    message_id = message_id or '1'

    return {
        'MessageId': '%s' % message_id,
        'ReceiptHandle': '1',
        'MD5OfBody': '123',
        'Body': (
            "StackName='%s'\n"
            "ResourceStatus='%s'\n"
            ""
        ) % (stack_name, status),
        'Attributes': {
            'string': 'string'
        },
        'MD5OfMessageAttributes': 'string',
        'MessageAttributes': {
            'string': {
                'StringValue': 'string',
                'BinaryValue': b'bytes',
                'StringListValues': [
                    'string',
                ],
                'BinaryListValues': [
                    b'bytes',
                ],
                'DataType': 'string'
            }
        }
    }


def create_fake_message(stack_name, status, message_id=None):

    return Message(create_fake_message_data(
        stack_name,
        status,
        message_id=message_id
    ))


class TestRetryThrottling(unittest.TestCase):

    def test_retry_on_throttling(self):

        s3 = boto3.client('s3', region_name='us-east-1')

        retry_stub = Stubber(s3)

        retry_stub.add_client_error(
            'list_buckets',
            service_error_code='Throttling',
            http_status_code=400,
            service_error_meta=None,
        )

        retry_stub.add_response('list_buckets', {
            'Buckets': [],
            'Owner': {
                'DisplayName': 'tom',
                'ID': '1'
            }
        })

        with retry_stub:
            retry_on_throttling(s3.list_buckets)

    def test_retry_on_throttling_fail(self):

        s3 = boto3.client('s3', region_name='us-east-1')

        retry_stub = Stubber(s3)

        retry_stub.add_client_error(
            'list_buckets',
            service_error_code='Throttling',
            http_status_code=401,
            service_error_meta=None,
        )

        retry_stub.add_response('list_buckets', {
            'Buckets': [],
            'Owner': {
                'DisplayName': 'tom',
                'ID': '1'
            }
        })

        with retry_stub:
            with self.assertRaises(botocore.exceptions.ClientError):
                retry_on_throttling(s3.list_buckets)


class TestMessage(unittest.TestCase):

    def test_parse_message(self):
        sample_fake = create_fake_message_data("bob", "CREATE_COMPLETE")
        data = parse_message(sample_fake)
        self.assertEqual(data['StackName'], "bob")
        self.assertEqual(data['ResourceStatus'], "CREATE_COMPLETE")

    def test_hello(self):
        sample_fake = create_fake_message_data("bob", "DELETE_COMPLETE")
        message = Message(sample_fake)
        self.assertEqual(message.StackName, "bob")
        self.assertEqual(message.ResourceStatus, "DELETE_COMPLETE")
        self.assertEqual(message.MessageId, sample_fake['MessageId'])


def get_policy(queue_arn, topic_arn):
    return """{
              "Version":"2012-10-17",
              "Statement":[
                {
                  "Sid":"SNSCloudPolicy",
                  "Effect":"Allow",
                  "Principal":"*",
                  "Action":"sqs:SendMessage",
                  "Resource":"%s",
                  "Condition":{
                    "ArnEquals":{
                      "aws:SourceArn":"%s"
                    }
                  }
                }
              ]
            }""" % (queue_arn, topic_arn)


class TestCloudListener(unittest.TestCase):

    def setUp(self):
        session = boto3.session.Session(
            region_name='us-east-1'
        )

        queue_name = "toms_queue"
        topic_name = "toms_topic"

        self.listener = CloudListener(
            queue_name,
            topic_name,
            session
        )

        self.sns_stub = Stubber(self.listener.sns)
        self.sqs_stub = Stubber(self.listener.sqs)

    def test_create_listener(self):

        self.sns_stub.activate()
        self.sqs_stub.activate()

        self.sns_stub.add_response('create_topic', {
            'TopicArn': 'toms-sns-topic'
        })

        self.sqs_stub.add_response('create_queue', {
            'QueueUrl': 'toms-queue-url'
        })

        self.sqs_stub.add_response('get_queue_attributes', {
            'Attributes': {
                'QueueArn': 'toms-queue-arn'
            }
        })

        self.sqs_stub.add_response('set_queue_attributes', {})

        self.sns_stub.add_response('subscribe', {
            'SubscriptionArn': 'toms-subscription-arn'
        })

        self.sns_stub.add_response('set_subscription_attributes', {})

        self.listener.setup()

        self.assertEqual(self.listener.topic_arn, 'toms-sns-topic')
        self.assertEqual(self.listener.queue_arn, 'toms-queue-arn')
        self.assertEqual(
            self.listener.create_policy(),
            get_policy('toms-queue-arn', 'toms-sns-topic')
        )

    def test_get_messages(self):
        self.sqs_stub.activate()
        self.listener.queue_url = "example"

        self.sqs_stub.add_response('receive_message', {
            "Messages": [
                {"Body": "StackId='stack1'\n"},
                {"Body": "StackId='stack2'\n"},
                {"Body": "StackId='stack3'\n"}
            ]
        }, {
            "AttributeNames": ["All"],
            "QueueUrl": "example",
            "WaitTimeSeconds": 20
        })

        messages = self.listener.get_messages()

        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0].StackId, 'stack1')

        self.sqs_stub.add_response('receive_message', {
            "Messages": []
        }, {
            "AttributeNames": ["All"],
            "QueueUrl": "example",
            "WaitTimeSeconds": 20
        })

        messages = self.listener.get_messages()

        self.assertEqual(len(messages), 0)

    def test_delete_messages(self):
        self.sqs_stub.activate()
        self.listener.queue_url = "example"

        messages = [
            Message({"Body": "", "ReceiptHandle": "m1", "EventId": "1"}),
            Message({"Body": "", "ReceiptHandle": "m2", "EventId": "2"}),
            Message({"Body": "", "ReceiptHandle": "m3", "EventId": "3"})
        ]

        self.sqs_stub.add_response('delete_message_batch', {
            'Successful': [
                {'Id': '1'},
                {'Id': '2'},
                {'Id': '3'}
            ],
            'Failed': []
        }, {'Entries': [{'Id': '1', 'ReceiptHandle': 'm1'},
                        {'Id': '2', 'ReceiptHandle': 'm2'},
                        {'Id': '3', 'ReceiptHandle': 'm3'}],
            'QueueUrl': 'example'})

        self.listener.delete_messages(messages)

        self.sqs_stub.add_response('delete_message_batch', {
            'Successful': [
                {'Id': '2'},
                {'Id': '3'}
            ],
            'Failed': [
                {
                    'Id': '1',
                    'SenderFault': True,
                    'Code': '1',
                    'Message': 'bad'
                },
            ]
        }, {'Entries': [{'Id': '1', 'ReceiptHandle': 'm1'},
                        {'Id': '2', 'ReceiptHandle': 'm2'},
                        {'Id': '3', 'ReceiptHandle': 'm3'}],
            'QueueUrl': 'example'})

        with self.assertRaises(ValueError):
            self.listener.delete_messages(messages)

    def test_cleanup(self):
        with self.sqs_stub:
            self.listener.queue_url = "example"

            self.sqs_stub.add_response('delete_queue', {}, {
                'QueueUrl': self.listener.queue_url
            })

            self.listener.cleanup()


class TestProvider(unittest.TestCase):

    def setUp(self):
        self.provider = Provider('us-east-1', 'toms-namespace')
        cfn = self.provider.cloudformation
        self.cfn_stubber = Stubber(cfn)

    def test_listener(self):
        with patch('stacker.providers.aws.default.CloudListener') as mockCloud:
            instance = mockCloud.return_value
            instance.setup = MagicMock()
            self.provider.listener
            self.provider.listener
            self.provider.listener
            mockCloud.assert_called_once()
            instance.setup.assert_called_once()

    def test_poll_events(self):
        self.provider._listener = MagicMock()

        self.provider.listener.get_messages.return_value = [
            create_fake_message('stack1', 'CREATE_COMPLETE'),
            create_fake_message('stack2', 'CREATE_IN_PROGRESS')
        ]

        status_dict = self.provider.poll_events(False)

        self.assertEqual(status_dict['stack1'], CompleteStatus)
        self.assertEqual(status_dict['stack2'], SubmittedStatus)

    def test_poll_events_tail(self):
        self.provider._listener = MagicMock()

        self.provider.listener.get_messages.return_value = [
            create_fake_message('stack1', 'CREATE_COMPLETE'),
            create_fake_message('stack1', 'CREATE_COMPLETE'),
        ]

        with patch('stacker.providers.aws.default.tail_print') as tailMock:
            self.provider.poll_events(True)
            tailMock.assert_called()

    def test_cleanup(self):
        self.provider._listener = MagicMock()
        self.provider.listener.cleanup = MagicMock()

        self.provider.cleanup()

        self.assertEqual(
            self.provider.listener.cleanup.called,
            True
        )

    def test_get_status(self):

        status_tests = [
            {
                'status': 'CREATE_IN_PROGRESS',
                'expected': SubmittedStatus
            },
            {
                'status': 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                'expected': SubmittedStatus
            },
            {
                'status': 'UPDATE_IN_PROGRESS',
                'expected': SubmittedStatus
            },
            {
                'status': 'DELETE_IN_PROGRESS',
                'expected': SubmittedStatus
            },
            {
                'status': 'CREATE_COMPLETE',
                'expected': CompleteStatus
            },
            {
                'status': 'UPDATE_COMPLETE',
                'expected': CompleteStatus
            },
            {
                'status': 'DELETE_COMPLETE',
                'expected': CompleteStatus
            }
        ]

        for status_test in status_tests:
            message = create_fake_message(
                'example',
                status_test['status']
            )
            status = self.provider.get_status(message)
            self.assertEqual(status, status_test['expected'])

    def test_unknown_status(self):
        message = create_fake_message(
            'example',
            'DOES_NOT_EXIST'
        )

        with self.assertRaises(exceptions.UnknownStatus):
            self.provider.get_status(message)

    def test_destroy_stack(self):

        with self.cfn_stubber:

            self.cfn_stubber.add_response('delete_stack', {}, {
                'StackName': 'example_stack'
            })

            self.provider.destroy_stack('example_stack')

            self.cfn_stubber.add_client_error(
                'delete_stack',
                service_error_code='1',
                service_message='stack does not exist',
                http_status_code=400,
                service_error_meta=None,
                expected_params={
                    'StackName': 'example_stack'
                }
            )

            with self.assertRaises(exceptions.StackDoesNotExist):
                self.provider.destroy_stack('example_stack')

    def test_create_stacker(self):

        with self.cfn_stubber:

            self.provider._listener = MagicMock()

            self.cfn_stubber.add_response('create_stack', {
                'StackId': 'bob'
            }, {
                'StackName': 'stack_name',
                'TemplateURL': 'template_url',
                'Parameters': [],
                'Tags': [],
                'Capabilities': ['CAPABILITY_NAMED_IAM'],
                'NotificationARNs': ['topic_arn']
            })

            self.provider.listener.topic_arn = 'topic_arn'

            self.provider.create_stack(
                'stack_name',
                'template_url',
                [],
                []
            )

    def test_get_stack(self):

        with self.cfn_stubber:

            self.cfn_stubber.add_response('describe_stacks', {
                'Stacks': [
                    {
                        'StackId': 'string',
                        'StackName': 'string',
                        'ChangeSetId': 'string',
                        'Description': 'string',
                        'Parameters': [
                            {
                                'ParameterKey': 'string',
                                'ParameterValue': 'string',
                                'UsePreviousValue': True
                            },
                        ],
                        'CreationTime': datetime(2015, 1, 1),
                        'LastUpdatedTime': datetime(2015, 1, 1),
                        'StackStatus': 'CREATE_IN_PROGRESS',
                        'StackStatusReason': 'string',
                        'DisableRollback': True,
                        'NotificationARNs': [
                            'string',
                        ],
                        'TimeoutInMinutes': 123,
                        'Capabilities': [
                            'CAPABILITY_NAMED_IAM',
                        ],
                        'Outputs': [
                            {
                                'OutputKey': 'string',
                                'OutputValue': 'string',
                                'Description': 'string'
                            },
                        ],
                        'RoleARN': 'arn:aws:sts::123456789012:'
                        'assumed-role/Accounting-Role/Mary',
                        'Tags': [
                            {
                                'Key': 'string',
                                'Value': 'string'
                            },
                        ]
                    },
                ],
                'NextToken': 'string'
            }, {
                'StackName': 'stack_name'
            })

            self.provider.get_stack('stack_name')

            self.cfn_stubber.add_client_error(
                'describe_stacks',
                service_error_code='1',
                service_message='stack does not exist',
                http_status_code=400,
                service_error_meta=None,
                expected_params={
                    'StackName': 'stack_name'
                }
            )

            with self.assertRaises(exceptions.StackDoesNotExist):
                self.provider.get_stack('stack_name')

    def test_update_stack(self):

        with self.cfn_stubber:

            self.provider._listener = MagicMock()

            self.cfn_stubber.add_response('update_stack', {
                'StackId': 'bob'
            }, {
                'StackName': 'stack_name',
                'TemplateURL': 'template_url',
                'Parameters': [],
                'Tags': [],
                'Capabilities': ['CAPABILITY_NAMED_IAM'],
                'NotificationARNs': ['topic_arn']
            })

            self.provider.listener.topic_arn = 'topic_arn'

            self.provider.update_stack(
                'stack_name',
                'template_url',
                [],
                []
            )

            self.cfn_stubber.add_client_error(
                'update_stack',
                service_error_code='1',
                service_message='stack does not exist',
                http_status_code=400,
                service_error_meta=None
            )

            with self.assertRaises(exceptions.StackDoesNotExist):
                self.provider.update_stack(
                    'stack_name',
                    'template_url',
                    [],
                    []
                )

            self.cfn_stubber.add_client_error(
                'update_stack',
                service_error_code='1',
                service_message='No updates are to be performed.',
                http_status_code=400,
                service_error_meta=None
            )

            with self.assertRaises(exceptions.StackDidNotChange):
                self.provider.update_stack(
                    'stack_name',
                    'template_url',
                    [],
                    []
                )

    def test_try_get_outputs(self):

        self.provider.get_stack = MagicMock()

        self.provider.get_stack.return_value = {
            'StackName': 'stack_name',
            'Outputs': [
                {
                    'OutputKey': 'testkey',
                    'OutputValue': 'testvalue'
                }
            ]
        }

        res = self.provider.try_get_outputs('stack_name')

        self.assertEqual(res, {'testkey': 'testvalue'})

    def test_try_get_outputs_fail(self):

        self.provider.get_stack = MagicMock()

        self.provider.get_stack.return_value = {}

        with self.assertRaises(KeyError):
            self.provider.try_get_outputs('stack_name')

    def test_get_outputs(self):

        self.provider.try_get_outputs = MagicMock()

        self.provider.try_get_outputs.return_value = {'bob': 'rob'}

        res = self.provider.get_outputs('stack_name')

        self.assertEqual(res, {'bob': 'rob'})

    def test_get_outputs_error(self):
        # Test retry on key error

        self.provider.try_get_outputs = MagicMock()

        self.provider.try_get_outputs.side_effect = [
            KeyError('boom'),
            {'bob': 'rob'}
        ]

        res = self.provider.get_outputs('stack_name')

        self.assertEqual(res, {'bob': 'rob'})

    def test_cleanup_stack(self):
        self.provider._listener = MagicMock()
        self.provider._listener.cleanup = MagicMock()
        self.provider.cleanup()
        self.provider._listener.cleanup.assert_called()

    def test_get_stack_info(self):

        with self.cfn_stubber:

            self.cfn_stubber.add_response('get_template', {
                'TemplateBody': json.dumps({
                    'resource': 'name'
                })
            })

            self.provider.get_stack = MagicMock()

            self.provider.get_stack.return_value = {
                'Parameters': [
                    {
                        'ParameterKey': 'testKey',
                        'ParameterValue': 'testValue'
                    }
                ]
            }

            res = self.provider.get_stack_info('stack_name')

            self.assertEqual(res, [
                '{"resource": "name"}',
                {'testKey': 'testValue'}
            ])

    def test_get_stack_info_error(self):

        with self.cfn_stubber:

            self.cfn_stubber.add_client_error(
                'get_template',
                service_error_code='1',
                service_message='stack does not exist',
                http_status_code=400,
                service_error_meta=None
            )

            self.provider.get_stack = MagicMock()

            self.provider.get_stack.return_value = {
                'Parameters': [
                    {
                        'ParameterKey': 'testKey',
                        'ParameterValue': 'testValue'
                    }
                ]
            }

            with self.assertRaises(exceptions.StackDoesNotExist):
                self.provider.get_stack_info('stack_name')
