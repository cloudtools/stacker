from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()

import unittest

import mock

import botocore.exceptions
from botocore.stub import Stubber, ANY

from stacker.actions.base import (
    BaseAction
)
from stacker.blueprints.base import Blueprint
from stacker.providers.aws.default import Provider
from stacker.session_cache import get_session

from stacker.tests.factories import (
    MockProviderBuilder,
    mock_context,
)

MOCK_VERSION = "01234abcdef"


class TestBlueprint(Blueprint):
    @property
    def version(self):
        return MOCK_VERSION

    VARIABLES = {
        "Param1": {"default": "default", "type": str},
    }


class TestBaseAction(unittest.TestCase):
    def test_ensure_cfn_bucket_exists(self):
        session = get_session("us-east-1")
        provider = Provider(session)
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider_builder=MockProviderBuilder(provider)
        )
        stubber = Stubber(action.s3_conn)
        stubber.add_response(
            "head_bucket",
            service_response={},
            expected_params={
                "Bucket": ANY,
            }
        )
        with stubber:
            action.ensure_cfn_bucket()

    def test_ensure_cfn_bucket_doesnt_exist_us_east(self):
        session = get_session("us-east-1")
        provider = Provider(session)
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider_builder=MockProviderBuilder(provider)
        )
        stubber = Stubber(action.s3_conn)
        stubber.add_client_error(
            "head_bucket",
            service_error_code="NoSuchBucket",
            service_message="Not Found",
            http_status_code=404,
        )
        stubber.add_response(
            "create_bucket",
            service_response={},
            expected_params={
                "Bucket": ANY,
            }
        )
        with stubber:
            action.ensure_cfn_bucket()

    def test_ensure_cfn_bucket_doesnt_exist_us_west(self):
        session = get_session("us-west-1")
        provider = Provider(session)
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider_builder=MockProviderBuilder(provider, region="us-west-1")
        )
        stubber = Stubber(action.s3_conn)
        stubber.add_client_error(
            "head_bucket",
            service_error_code="NoSuchBucket",
            service_message="Not Found",
            http_status_code=404,
        )
        stubber.add_response(
            "create_bucket",
            service_response={},
            expected_params={
                "Bucket": ANY,
                "CreateBucketConfiguration": {
                    "LocationConstraint": "us-west-1",
                }
            }
        )
        with stubber:
            action.ensure_cfn_bucket()

    def test_ensure_cfn_forbidden(self):
        session = get_session("us-west-1")
        provider = Provider(session)
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider_builder=MockProviderBuilder(provider)
        )
        stubber = Stubber(action.s3_conn)
        stubber.add_client_error(
            "head_bucket",
            service_error_code="AccessDenied",
            service_message="Forbidden",
            http_status_code=403,
        )
        with stubber:
            with self.assertRaises(botocore.exceptions.ClientError):
                action.ensure_cfn_bucket()

    def test_stack_template_url(self):
        context = mock_context("mynamespace")
        blueprint = TestBlueprint(name="myblueprint", context=context)

        region = "us-east-1"
        endpoint = "https://example.com"
        session = get_session(region)
        provider = Provider(session)
        action = BaseAction(
            context=context,
            provider_builder=MockProviderBuilder(provider, region=region)
        )

        with mock.patch('stacker.actions.base.get_s3_endpoint', autospec=True,
                        return_value=endpoint):
            self.assertEqual(
                action.stack_template_url(blueprint),
                "%s/%s/stack_templates/%s/%s-%s.json" % (
                    endpoint,
                    "stacker-mynamespace",
                    "mynamespace-myblueprint",
                    "myblueprint",
                    MOCK_VERSION
                )
            )
