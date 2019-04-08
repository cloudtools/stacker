from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from moto import mock_ecs
from testfixtures import LogCapture

from stacker.hooks.ecs import create_clusters
from ..factories import mock_boto3_client, mock_context, mock_provider


REGION = "us-east-1"


class TestECSHooks(unittest.TestCase):

    def setUp(self):
        self.provider = mock_provider(region=REGION)
        self.context = mock_context(namespace="fake")

        self.mock_ecs = mock_ecs()
        self.mock_ecs.start()
        self.ecs, self.ecs_mock = mock_boto3_client("ecs", region=REGION)
        self.ecs_mock.start()

    def tearDown(self):
        self.ecs_mock.stop()
        self.mock_ecs.stop()

    def test_create_single_cluster(self):
        cluster = "test-cluster"
        logger = "stacker.hooks.ecs"
        response = self.ecs.list_clusters()

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

        response = self.ecs.list_clusters()
        self.assertEqual(len(response["clusterArns"]), 1)

    def test_create_multiple_clusters(self):
        clusters = ("test-cluster0", "test-cluster1")
        logger = "stacker.hooks.ecs"
        response = self.ecs.list_clusters()

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

        response = self.ecs.list_clusters()
        self.assertEqual(len(response["clusterArns"]), 2)

    def test_fail_create_cluster(self):
        logger = "stacker.hooks.ecs"
        response = self.ecs.list_clusters()

        self.assertEqual(len(response["clusterArns"]), 0)
        with LogCapture(logger) as logs:
            create_clusters(
                provider=self.provider,
                context=self.context
            )

            logs.check(
                (
                    logger,
                    "ERROR",
                    "setup_clusters hook missing \"clusters\" argument"
                )
            )

        response = self.ecs.list_clusters()
        self.assertEqual(len(response["clusterArns"]), 0)
