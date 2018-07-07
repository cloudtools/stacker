from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

import boto3
from moto import mock_ecs
from testfixtures import LogCapture

from stacker.hooks.ecs import create_clusters
from ..factories import (
    mock_context,
    mock_provider,
)

REGION = "us-east-1"


class TestECSHooks(unittest.TestCase):

    def setUp(self):
        self.provider = mock_provider(region=REGION)
        self.context = mock_context(namespace="fake")

    def test_create_single_cluster(self):
        with mock_ecs():
            cluster = "test-cluster"
            logger = "stacker.hooks.ecs"
            client = boto3.client("ecs", region_name=REGION)
            response = client.list_clusters()

            self.assertEqual(len(response["clusterArns"]), 0)
            with LogCapture(logger) as logs:
                self.assertTrue(
                    create_clusters(
                        provider=self.provider,
                        context=self.context,
                        clusters=cluster,
                    )
                )

                logs.check(
                    (
                        logger,
                        "DEBUG",
                        "Creating ECS cluster: %s" % cluster
                    )
                )

            response = client.list_clusters()
            self.assertEqual(len(response["clusterArns"]), 1)

    def test_create_multiple_clusters(self):
        with mock_ecs():
            clusters = ("test-cluster0", "test-cluster1")
            logger = "stacker.hooks.ecs"
            client = boto3.client("ecs", region_name=REGION)
            response = client.list_clusters()

            self.assertEqual(len(response["clusterArns"]), 0)
            for cluster in clusters:
                with LogCapture(logger) as logs:
                    self.assertTrue(
                        create_clusters(
                            provider=self.provider,
                            context=self.context,
                            clusters=cluster,
                        )
                    )

                    logs.check(
                        (
                            logger,
                            "DEBUG",
                            "Creating ECS cluster: %s" % cluster
                        )
                    )

            response = client.list_clusters()
            self.assertEqual(len(response["clusterArns"]), 2)
