from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object

import mock

import boto3

from stacker.context import Context
from stacker.config import Config, Stack
from stacker.exceptions import StackDoesNotExist, StackUpdateBadStatus
from stacker.providers.base import BaseProvider


class MockThreadingEvent(object):
    def wait(self, timeout=None):
        return False


class MockProviderBuilder(object):
    def __init__(self, provider, region=None):
        self.provider = provider
        self.region = region

    def build(self, region=None, profile=None):
        return self.provider


class MockProvider(BaseProvider):
    def __init__(self, outputs=None, region=None, profile=None):
        self.region = region
        self.profile = profile

        self._stacks = {}
        for stack_name, stack_outputs in (outputs or {}).items():
            self._stacks[stack_name] = {
                "StackName": stack_name,
                "Outputs": stack_outputs,
                "StackStatus": "CREATED"
            }
        self._sessions = {}

    def get_stack(self, stack_name, **kwargs):
        try:
            return self._stacks[stack_name]
        except KeyError:
            raise StackDoesNotExist(stack_name)

    def get_outputs(self, stack_name, *args, **kwargs):
        return self.get_stack(stack_name)["Outputs"]

    def get_stack_status(self, stack_name, *args, **kwargs):
        return self.get_stack(stack_name)["StackStatus"]

    def create_stack(self, stack_name, *args, **kwargs):
        try:
            stack = self.get_stack(stack_name)
            status = self.get_stack_status(stack)
            if status != "DELETED":
                raise StackUpdateBadStatus(stack_name, status, "can't create")
        except StackDoesNotExist:
            pass

        return None

    def update_stack(self, stack_name, *args, **kwargs):
        stack = self.get_stack(stack_name)
        status = self.get_stack_status(stack)
        if status == "DELETED":
            raise StackUpdateBadStatus(stack_name, status, "can't update")

        stack["StackStatus"] = "UPDATED"
        return None

    def destroy_stack(self, stack_name, *args, **kwargs):
        stack = self.get_stack(stack_name)
        status = self.get_stack_status(stack)
        if status == "DELETED":
            raise StackUpdateBadStatus(stack_name, status, "can't destroy")

        stack["StackStatus"] = "DELETED"
        return None

    def get_session(self, region=None, profile=None):
        return boto3.Session(region_name=region or self.region,
                             profile_name=profile or self.profile)


def mock_provider(outputs=None, region=None, profile=None, **kwargs):
    provider = MockProvider(outputs, region=region, profile=profile)
    return provider


def mock_context(namespace="default", extra_config_args=None,
                 environment=None, **kwargs):
    config_args = {"namespace": namespace}
    if extra_config_args:
        config_args.update(extra_config_args)

    config = Config(config_args)
    environment = environment or {}
    return Context(config=config, environment=environment, **kwargs)


def mock_boto3_client(service_name, region=None, profile=None):
    client = boto3.client(service_name, region_name=region)
    default_session = boto3._get_default_session()

    region = region or default_session.region_name
    profile = profile or default_session.profile_name
    svc_name = service_name

    def create_client(self, service_name, region_name=None, **kwargs):
        region_name = region_name or self.region_name
        profile_name = self.profile_name
        if (svc_name, region, profile) == \
                (service_name, region_name, profile_name):
            return client

        raise AssertionError(
            "Attempted to create non-mocked AWS client: service={} region={} "
            "profile={}".format(service_name, region_name, profile_name))

    mock_ = mock.patch('boto3.Session.client', autospec=True,
                       side_effect=create_client)
    return client, mock_


def generate_definition(base_name, stack_id, **overrides):
    definition = {
        "name": "%s.%d" % (base_name, stack_id),
        "class_path": "stacker.tests.fixtures.mock_blueprints.%s" % (
            base_name.upper()),
        "requires": []
    }
    definition.update(overrides)
    return Stack(definition)


class SessionStub(object):

    """Stubber class for boto3 sessions made with session_cache.get_session()

    This is a helper class that should be used when trying to stub out
    get_session() calls using the boto3.stubber.

    Example Usage:

        @mock.patch('stacker.lookups.handlers.myfile.get_session',
                return_value=sessionStub(client))
        def myfile_test(self, client_stub):
            ...

    Attributes:
        client_stub (:class:`boto3.session.Session`:): boto3 session stub

    """

    def __init__(self, client_stub):
        self.client_stub = client_stub

    def client(self, region):
        """Returns the stubbed client object

        Args:
            region (str): So boto3 won't complain

        Returns:
            :class:`boto3.session.Session`: The stubbed boto3 session
        """
        return self.client_stub
