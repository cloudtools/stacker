from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
from mock import patch

import boto3
from moto import mock_ec2
from testfixtures import LogCapture

from stacker.hooks.keypair import ensure_keypair_exists, find
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
            logger = "stacker.hooks.keypair"
            client = boto3.client("ec2", region_name=REGION)
            response = client.describe_key_pairs()

            # initially no key pairs created
            self.assertEqual(len(response["KeyPairs"]), 0)
            with LogCapture(logger) as logs:
                self.assertFalse(ensure_keypair_exists(provider=self.provider,
                                                       context=self.context,
                                                       keypair=KEY_PAIR_NAME))
                logs.check(
                    (
                        logger,
                        "INFO",
                        "keypair: \"%s\" not found" % KEY_PAIR_NAME
                    ),
                    (
                        logger,
                        "WARNING",
                        "no action to find keypair, failing"
                    )
                )

    def test_keypair_exists(self):
        with mock_ec2():
            logger = "stacker.hooks.keypair"
            client = boto3.client("ec2", region_name=REGION)
            client.create_key_pair(KeyName=KEY_PAIR_NAME)
            response = client.describe_key_pairs()

            # check that one keypair was created
            self.assertEqual(len(response["KeyPairs"]), 1)
            keypair = find(response["KeyPairs"], "KeyName", KEY_PAIR_NAME)
            with LogCapture(logger) as logs:
                value = ensure_keypair_exists(provider=self.provider,
                                              context=self.context,
                                              keypair=KEY_PAIR_NAME)
                message = "keypair: " + KEY_PAIR_NAME + \
                          " (" + keypair["KeyFingerprint"] + ") exists"
                logs.check(
                    (
                        logger,
                        "INFO",
                        message
                    )
                )
                self.assertEqual(value["status"], "exists")
                self.assertEqual(value["key_name"], KEY_PAIR_NAME)
                self.assertEqual(value["fingerprint"],
                                 keypair["KeyFingerprint"])

    @patch("stacker.hooks.keypair.input", create=True)
    def test_keypair_missing_create(self, mocked_input):
        mocked_input.side_effect = ["create", "./"]
        with mock_ec2():
            logger = "stacker.hooks.keypair"
            client = boto3.client("ec2", region_name=REGION)
            with LogCapture(logger) as logs:
                value = ensure_keypair_exists(provider=self.provider,
                                              context=self.context,
                                              keypair=KEY_PAIR_NAME)
                response = client.describe_key_pairs()
                print(response)
                keypair = find(response["KeyPairs"], "KeyName", KEY_PAIR_NAME)
                logs.check(
                    (
                        logger,
                        "INFO",
                        "keypair: \"%s\" not found" % KEY_PAIR_NAME
                    ),
                    (
                        logger,
                        "INFO",
                        "keypair: " + KEY_PAIR_NAME + " (" + keypair["KeyFingerprint"] + ") created"
                    )
                )
            self.assertEqual(value["status"], "created")
            self.assertEqual(value["key_name"], KEY_PAIR_NAME)
            self.assertEqual(value["file_path"],
                             "/home/circleci/project/"
                             + KEY_PAIR_NAME + ".pem")

    @patch("stacker.hooks.keypair.input", create=True)
    def test_keypair_missing_create_invalid_path(self, mocked_input):
        mocked_input.side_effect = ["create", "$"]
        with mock_ec2():
            logger = "stacker.hooks.keypair"
            with LogCapture(logger) as logs:
                value = ensure_keypair_exists(provider=self.provider,
                                              context=self.context,
                                              keypair=KEY_PAIR_NAME)
                logs.check(
                    (
                        logger,
                        "INFO",
                        "keypair: \"%s\" not found" % KEY_PAIR_NAME
                    ),
                    (
                        logger,
                        "ERROR",
                        "\"/home/circleci/project/"
                        + "$" + "\" is not a valid directory"
                    )
                )
                self.assertFalse(value)

    @patch("stacker.hooks.keypair.input", create=True)
    def test_keypair_missing_import_invalid_path(self, mocked_input):
        mocked_input.side_effect = ["import", "$"]
        with mock_ec2():
            logger = "stacker.hooks.keypair"
            with LogCapture(logger) as logs:
                value = ensure_keypair_exists(provider=self.provider,
                                              context=self.context,
                                              keypair=KEY_PAIR_NAME)
                logs.check(
                    (
                        logger,
                        "INFO",
                        "keypair: \"%s\" not found" % KEY_PAIR_NAME
                    ),
                    (
                        logger,
                        "ERROR",
                        "Failed to find keypair at path: "
                        + "/home/circleci/project/$"
                    )
                )
                self.assertFalse(value)
