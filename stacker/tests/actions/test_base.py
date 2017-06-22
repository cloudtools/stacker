import unittest

import boto3
from botocore.stub import Stubber, ANY
import botocore.exceptions

from stacker.actions.base import (
    get_client_region,
    get_s3_endpoint,
    s3_create_bucket_location_constraint,
    BaseAction
)

from stacker.providers.aws.default import Provider

from stacker.tests.factories import (
    mock_context,
)


class TestBaseActionFunctions(unittest.TestCase):
    def test_get_client_region(self):
        regions = ["us-east-1", "us-west-1", "eu-west-1", "sa-east-1"]
        for region in regions:
            client = boto3.client("s3", region_name=region)
            self.assertEqual(get_client_region(client), region)

    def test_get_s3_endpoint(self):
        endpoint_map = {
            "us-east-1": "https://s3.amazonaws.com",
            "us-west-1": "https://s3-us-west-1.amazonaws.com",
            "eu-west-1": "https://s3-eu-west-1.amazonaws.com",
            "sa-east-1": "https://s3-sa-east-1.amazonaws.com",
        }

        for region in endpoint_map:
            client = boto3.client("s3", region_name=region)
            self.assertEqual(get_s3_endpoint(client), endpoint_map[region])

    def test_s3_create_bucket_location_constraint(self):
        client = boto3.client("s3", region_name="us-east-1")
        self.assertEqual(s3_create_bucket_location_constraint(client), "")
        client = boto3.client("s3", region_name="us-west-1")
        self.assertEqual(
            s3_create_bucket_location_constraint(client),
            "us-west-1"
        )


class TestBaseAction(unittest.TestCase):
    def test_ensure_cfn_bucket_exists(self):
        provider = Provider("us-east-1")
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider=provider
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
        provider = Provider("us-east-1")
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider=provider
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
        provider = Provider("us-west-1")
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider=provider
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
        provider = Provider("us-west-1")
        action = BaseAction(
            context=mock_context("mynamespace"),
            provider=provider
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
