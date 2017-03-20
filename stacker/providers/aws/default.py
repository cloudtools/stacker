import json
import logging
import re
import botocore
import uuid
from ..base import BaseProvider
from ... import exceptions
from ...util import retry_with_backoff
from stacker.session_cache import get_session
from stacker.status import (
    SubmittedStatus,
    CompleteStatus,
)

logger = logging.getLogger(__name__)


def parse_message(message):
    """Parses cloudformation SNS message to grab event metdata"""
    msg_re = re.compile("(?P<key>[^=]+)='(?P<value>[^']*)'\n")
    body = message["Body"]
    data = dict(msg_re.findall(body))
    return data


class Message(object):

    """Message wrapper for cloudformation"""

    def __init__(self, metadata, parent_queue):

        self._parent_queue = parent_queue

        parsed_message = parse_message(metadata)

        for key, value in parsed_message.iteritems():
            setattr(self, key, value)

        for key, value in metadata.iteritems():
            setattr(self, key, value)


class CloudListener(object):

    """SNS/SQS listener for cloudformation build events"""

    def __init__(self, queue_name, topic_name, session):
        self.session = session
        self.queue_name = queue_name
        self.topic_name = topic_name

        # Create all the necessary cloudfromation resources
        self.setup()

    def create_policy(self):
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
            }""" % (self.queue_arn, self.topic_arn)

    def setup(self):
        """Creates the initial SNS/SQS resources for listening to
        cloudformation events"""

        logger.debug("Creating cloudformation listener")
        self.sns = self.session.client("sns")
        self.sqs = self.session.client("sqs")

        topic = self.sns.create_topic(Name=self.topic_name)
        self.topic_arn = topic["TopicArn"]

        queue = self.sqs.create_queue(
            QueueName=self.queue_name,
            Attributes={"MessageRetentionPeriod": "60"}
        )

        self.queue_url = queue["QueueUrl"]

        attr = self.sqs.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=["QueueArn"]
        )

        self.queue_arn = attr["Attributes"]["QueueArn"]

        self.sqs.set_queue_attributes(
            QueueUrl=self.queue_url,
            Attributes={
                "Policy": self.create_policy()
            }
        )

        result = self.sns.subscribe(
            TopicArn=self.topic_arn,
            Protocol="sqs",
            Endpoint=self.queue_arn
        )

        sub_arn = result["SubscriptionArn"]

        self.sns.set_subscription_attributes(
            SubscriptionArn=sub_arn,
            AttributeName="RawMessageDelivery",
            AttributeValue="true"
        )

        logger.debug('Done creating cloudformation event listeners')

    def get_messages(self):
        updates = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            AttributeNames=["All"],
            WaitTimeSeconds=20
        )

        return [Message(m, self) for m in updates.get("Messages", [])]

    def delete_messages(self, messages):
        receipts = []
        for m in messages:
            unique_id = str(uuid.uuid4())
            receipts.append({
                'Id': unique_id,
                'ReceiptHandle': m.ReceiptHandle
            })

        self.sqs.delete_message_batch(
            QueueUrl=self.queue_url,
            Entries=receipts
        )

    def cleanup(self):
        """Delete the sqs queue after each run of stacker. However
        the sns topic does not get deleted as it follows a consistent
        naming scheme of the form stacker-{namespace}."""

        logger.debug('Deleting cloud listener resources')

        self.sqs.delete_queue(
            QueueUrl=self.queue_url
        )

        logger.debug('Done deleting cloud listener resources')


def get_output_dict(stack):
    """Returns a dict of key/values for the outputs for a given CF stack.

    Args:
        stack (dict): The stack object to get
            outputs from.

    Returns:
        dict: A dictionary with key/values for each output on the stack.

    """
    outputs = {}
    for output in stack['Outputs']:
        logger.debug("    %s %s: %s", stack['StackName'], output['OutputKey'],
                     output['OutputValue'])
        outputs[output['OutputKey']] = output['OutputValue']
    return outputs


def retry_on_throttling(fn, attempts=3, args=None, kwargs=None):
    """Wrap retry_with_backoff to handle AWS Cloudformation Throttling.

    Args:
        fn (function): The function to call.
        attempts (int): Maximum # of attempts to retry the function.
        args (list): List of positional arguments to pass to the function.
        kwargs (dict): Dict of keyword arguments to pass to the function.

    Returns:
        passthrough: This returns the result of the function call itself.

    Raises:
        passthrough: This raises any exceptions the function call raises,
            except for boto.exception.BotoServerError, provided it doesn't
            retry more than attempts.
    """
    def _throttling_checker(exc):
        """

        Args:
        exc (botocore.exceptions.ClientError): Expected exception type

        Returns:
             boolean: indicating whether this error is a throttling error
        """
        if exc.response['ResponseMetadata']['HTTPStatusCode'] == 400 and \
                exc.response['Error']['Code'] == "Throttling":
            logger.debug("AWS throttling calls.")
            return True
        return False

    return retry_with_backoff(fn, args=args, kwargs=kwargs, attempts=attempts,
                              exc_list=(botocore.exceptions.ClientError, ),
                              retry_checker=_throttling_checker)


class Provider(BaseProvider):

    """AWS CloudFormation Provider"""

    IN_PROGRESS_STATUSES = (
        "CREATE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_IN_PROGRESS",
        "DELETE_IN_PROGRESS",
    )
    COMPLETE_STATUSES = (
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "DELETE_COMPLETE"
    )

    def __init__(self, region, namespace, **kwargs):
        self.region = region
        self._outputs = {}
        self._cloudformation = None
        self._listener = None
        self.namespace = namespace

    @property
    def cloudformation(self):
        if not self._cloudformation:
            session = get_session(self.region)
            self._cloudformation = session.client('cloudformation')

        return self._cloudformation

    @property
    def listener(self):
        if not self._listener:
            session = get_session(self.region)

            # This stays the same for stacker call in this namespace
            topic_name = self.namespace

            # Unique every time stacker is ran
            unique_sufix = str(uuid.uuid4())
            queue_name = "%s-%s" % (self.namespace, unique_sufix)

            self._listener = CloudListener(
                queue_name,
                topic_name,
                session
            )

        return self._listener

    def poll_events(self, tail):
        messages = self.listener.get_messages()
        status_dict = {}

        for message in messages:
            status_dict[message.StackName] = self.get_status(message)
            if tail:
                Provider._tail_print(message)

        if messages:
            self.listener.delete_messages(messages)

        return status_dict

    def cleanup(self):
        self.listener.cleanup()

    def get_status(self, message):
        status_name = message.ResourceStatus

        if status_name in self.COMPLETE_STATUSES:
            return CompleteStatus(status_name)
        elif status_name in self.IN_PROGRESS_STATUSES:
            return SubmittedStatus(status_name)

        raise exceptions.UnknownStatus(
            message.StackName,
            status_name,
            message.ResourceStatusReason
        )

    def destroy_stack(self, stack_name, **kwargs):
        logger.debug("Destroying stack: %s" % (stack_name))
        try:
            return retry_on_throttling(self.cloudformation.delete_stack,
                                       kwargs=dict(StackName=stack_name))

        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.message:
                raise exceptions.StackDoesNotExist(stack_name)

    def create_stack(self, fqn, template_url, parameters, tags, **kwargs):
        logger.debug("Stack %s not found, creating.", fqn)
        logger.debug("Using parameters: %s", parameters)
        logger.debug("Using tags: %s", tags)
        retry_on_throttling(
            self.cloudformation.create_stack,
            kwargs=dict(StackName=fqn,
                        TemplateURL=template_url,
                        Parameters=parameters,
                        Tags=tags,
                        Capabilities=["CAPABILITY_NAMED_IAM"],
                        NotificationARNs=[self.listener.topic_arn]),
        )
        return True

    def get_stack(self, stack_name):
        try:
            return retry_on_throttling(
                self.cloudformation.describe_stacks,
                kwargs=dict(StackName=stack_name))['Stacks'][0]
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

    def update_stack(self, fqn, template_url, parameters, tags, **kwargs):
        try:
            logger.debug("Attempting to update stack %s.", fqn)
            retry_on_throttling(
                self.cloudformation.update_stack,
                kwargs=dict(StackName=fqn,
                            TemplateURL=template_url,
                            Parameters=parameters,
                            Tags=tags,
                            Capabilities=["CAPABILITY_NAMED_IAM"],
                            NotificationARNs=[self.listener.topic_arn]),
            )
        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed." in e.message:
                logger.debug(
                    "Stack %s did not change, not updating.",
                    fqn,
                )
                raise exceptions.StackDidNotChange
            if "does not exist" in e.message:
                raise exceptions.StackDoesNotExist(fqn)
            raise
        return True

    def get_stack_name(self, stack, **kwargs):
        return stack["StackName"]

    def try_get_outputs(self, stack_name):
        """Attempt to get outputs from stack.

            Raises:
                KeyError: If the given stack contains no outputs yet
        """
        if stack_name not in self._outputs:
            stack = self.get_stack(stack_name)
            if "Outputs" not in stack:
                raise KeyError("No Outputs in Stack")
            self._outputs[stack_name] = get_output_dict(stack)

        return self._outputs[stack_name]

    def get_outputs(self, stack_name):
        """Gets a given stacks outputs

        Retries fetching the stack several times because cloudformation
        fires a CREATE_COMPLETE event before the stack actually gets updated
        with the correct values.
        """
        outputs = retry_with_backoff(
            self.try_get_outputs,
            args=[stack_name],
            exc_list=(KeyError, ),
            min_delay=0.2,
            max_delay=3
        )

        return outputs

    def get_stack_info(self, stack_name):
        """ Get the template and parameters of the stack currently in AWS

        Returns [ template, parameters ]
        """
        try:
            stacks = retry_on_throttling(
                self.cloudformation.describe_stacks,
                kwargs=dict(StackName=stack_name))
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

        try:
            template = retry_on_throttling(
                self.cloudformation.get_template,
                kwargs=dict(StackName=stack_name))["TemplateBody"]
        except botocore.exceptions.ClientError as e:
            if "does not exist" not in e.message:
                raise
            raise exceptions.StackDoesNotExist(stack_name)

        stack = stacks["Stacks"][0]
        parameters = dict()
        if "Parameters" in stack:
            for p in stack["Parameters"]:
                parameters[p["ParameterKey"]] = p["ParameterValue"]

        return [json.dumps(template), parameters]
