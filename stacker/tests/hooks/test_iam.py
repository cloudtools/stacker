import unittest

import boto3
from botocore.exceptions import ClientError

from moto import mock_iam

from stacker.hooks.iam import (
    create_ecs_service_role,
    _get_cert_arn_from_response,
)


REGION = "us-east-1"

# No test for stacker.hooks.iam.ensure_server_cert_exists until
# this PR is accepted in moto:
# https://github.com/spulec/moto/pull/679


class TestIAMHooks(unittest.TestCase):
    def test_get_cert_arn_from_response(self):
        arn = "fake-arn"
        # Creation response
        response = {
            "ServerCertificateMetadata": {
                "Arn": arn
            }
        }

        self.assertEqual(_get_cert_arn_from_response(response), arn)

        # Existing cert response
        response = {"ServerCertificate": response}
        self.assertEqual(_get_cert_arn_from_response(response), arn)

    def test_create_service_role(self):
        role_name = "ecsServiceRole"
        policy_name = "AmazonEC2ContainerServiceRolePolicy"
        with mock_iam():
            client = boto3.client("iam", region_name=REGION)

            with self.assertRaises(ClientError):
                client.get_role(RoleName=role_name)

            self.assertTrue(
                create_ecs_service_role(
                    region=REGION,
                    namespace="fake",
                    mappings={},
                    parameters={}
                )
            )

            role = client.get_role(RoleName=role_name)

            self.assertIn("Role", role)
            self.assertEqual(role_name, role["Role"]["RoleName"])
            client.get_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
