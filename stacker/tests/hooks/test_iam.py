from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from awacs.helpers.trust import get_ecs_assumerole_policy
from botocore.exceptions import ClientError
from moto import mock_iam

from stacker.hooks.iam import (
    create_ecs_service_role,
    _get_cert_arn_from_response,
)
from ..factories import mock_boto3_client, mock_context, mock_provider


REGION = "us-east-1"

# No test for stacker.hooks.iam.ensure_server_cert_exists until
# updated version of moto is imported
# (https://github.com/spulec/moto/pull/679) merged


class TestIAMHooks(unittest.TestCase):

    def setUp(self):
        self.context = mock_context(namespace="fake")
        self.provider = mock_provider(region=REGION)

        self.mock_iam = mock_iam()
        self.mock_iam.start()
        self.iam, self.client_mock = mock_boto3_client("iam", region=REGION)
        self.client_mock.start()

    def tearDown(self):
        self.client_mock.stop()
        self.mock_iam.stop()

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

        with self.assertRaises(ClientError):
            self.iam.get_role(RoleName=role_name)

        self.assertTrue(
            create_ecs_service_role(
                context=self.context,
                provider=self.provider,
            )
        )

        role = self.iam.get_role(RoleName=role_name)

        self.assertIn("Role", role)
        self.assertEqual(role_name, role["Role"]["RoleName"])

        self.iam.get_role_policy(
            RoleName=role_name,
            PolicyName=policy_name
        )

    def test_create_service_role_already_exists(self):
        role_name = "ecsServiceRole"
        policy_name = "AmazonEC2ContainerServiceRolePolicy"

        self.iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=get_ecs_assumerole_policy().to_json()
        )

        self.assertTrue(
            create_ecs_service_role(
                context=self.context,
                provider=self.provider,
            )
        )

        role = self.iam.get_role(RoleName=role_name)

        self.assertIn("Role", role)
        self.assertEqual(role_name, role["Role"]["RoleName"])
        self.iam.get_role_policy(
            RoleName=role_name,
            PolicyName=policy_name
        )
