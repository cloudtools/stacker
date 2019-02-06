from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
from mock import patch
from builtins import object
from builtins import input

import boto3
from moto import mock_ec2
from testfixtures import LogCapture

from stacker.hooks.keypair import ensure_keypair_exists
from ..factories import (
    mock_context,
    mock_provider,
)

REGION = "us-east-1"
KEY_PAIR_NAME = "FakeKey"


class TestKeypairHooks(unittest.TestCase):

    def setUp(self):
        self.provider = mock_provider(region=REGION)
        self.context = mock_context(namespace="fake")

    @patch("stacker.hooks.keypair.input", create=True)
    def test_keypair_missing_cancel_input(self, mocked_input):
        mocked_input.side_effect = ["Cancel"]
        with mock_ec2():
            logger = "stacker.hooks.ec2"
            client = boto3.client("ec2", region_name=REGION)
            response = client.describe_key_pairs()

            # initially no key pairs created
            self.assertEqual(len(response["KeyPairs"]), 0)
            with LogCapture(logger) as logs:
                self.assertFalse(ensure_keypair_exists(provider=self.provider, context=self.context, keypair="FakeKey"))
                logs.check(
                    (
                        logger,
                        "info",
                        "keypair: \"%s\" not found", KEY_PAIR_NAME
                    )
                )
