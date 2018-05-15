import unittest

from botocore.stub import Stubber, ANY
import botocore.exceptions

from stacker.actions.base import (
    BaseAction
)

from stacker.providers.aws.default import Provider
from stacker.blueprints.base import Blueprint
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
        test_cases = (
            ("us-east-1", "s3.amazonaws.com"),
            ("us-west-1", "s3.us-west-1.amazonaws.com"),
            ("eu-west-1", "s3.eu-west-1.amazonaws.com"),
            ("sa-east-1", "s3.sa-east-1.amazonaws.com"),
        )
        context = mock_context("mynamespace")
        blueprint = TestBlueprint(name="myblueprint", context=context)

        for region, endpoint in test_cases:
            session = get_session(region)
            provider = Provider(session)
            action = BaseAction(
                context=context,
                provider_builder=MockProviderBuilder(provider, region=region)
            )
            self.assertEqual(
                action.stack_template_url(blueprint),
                "https://%s/%s/stack_templates/%s/%s-%s.json" % (
                    endpoint,
                    "stacker-mynamespace",
                    "mynamespace-myblueprint",
                    "myblueprint",
                    MOCK_VERSION

                )
            )
