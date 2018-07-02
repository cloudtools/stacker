from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
from mock import MagicMock

from stacker.context import Context
from stacker.config import Config, Stack
from stacker.lookups import Lookup


class MockThreadingEvent(object):
    def wait(self, timeout=None):
        return False


class MockProviderBuilder(object):
    def __init__(self, provider, region=None):
        self.provider = provider
        self.region = region

    def build(self, region=None, profile=None):
        return self.provider


def mock_provider(**kwargs):
    return MagicMock(**kwargs)


def mock_context(namespace="default", extra_config_args=None, **kwargs):
    config_args = {"namespace": namespace}
    if extra_config_args:
        config_args.update(extra_config_args)
    config = Config(config_args)
    environment = kwargs.get("environment", {})
    return Context(
        config=config,
        environment=environment,
        **kwargs)


def generate_definition(base_name, stack_id, **overrides):
    definition = {
        "name": "%s.%d" % (base_name, stack_id),
        "class_path": "stacker.tests.fixtures.mock_blueprints.%s" % (
            base_name.upper()),
        "requires": []
    }
    definition.update(overrides)
    return Stack(definition)


def mock_lookup(lookup_input, lookup_type, raw=None):
    if raw is None:
        raw = "%s %s" % (lookup_type, lookup_input)
    return Lookup(type=lookup_type, input=lookup_input, raw=raw)


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
