from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest
import mock
from botocore.stub import Stubber
from stacker.lookups.handlers.ami import handler, ImageNotFound
import boto3
from stacker.tests.factories import SessionStub, mock_provider

REGION = "us-east-1"


class TestAMILookup(unittest.TestCase):
    client = boto3.client("ec2", region_name=REGION)

    def setUp(self):
        self.stubber = Stubber(self.client)
        self.provider = mock_provider(region=REGION)

    @mock.patch("stacker.lookups.handlers.ami.get_session",
                return_value=SessionStub(client))
    def test_basic_lookup_single_image(self, mock_client):
        image_id = "ami-fffccc111"
        self.stubber.add_response(
            "describe_images",
            {
                "Images": [
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-13T01:17:44.000Z",
                        "State": "available",
                        "ImageId": image_id,
                        "Name": "Fake Image 1",
                        "VirtualizationType": "hvm",
                    }
                ]
            }
        )

        with self.stubber:
            value = handler(
                value="owners:self name_regex:Fake\sImage\s\d",
                provider=self.provider
            )
            self.assertEqual(value, image_id)

    @mock.patch("stacker.lookups.handlers.ami.get_session",
                return_value=SessionStub(client))
    def test_basic_lookup_with_region(self, mock_client):
        image_id = "ami-fffccc111"
        self.stubber.add_response(
            "describe_images",
            {
                "Images": [
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-13T01:17:44.000Z",
                        "State": "available",
                        "ImageId": image_id,
                        "Name": "Fake Image 1",
                        "VirtualizationType": "hvm",
                    }
                ]
            }
        )

        with self.stubber:
            value = handler(
                value="us-west-1@owners:self name_regex:Fake\sImage\s\d",
                provider=self.provider
            )
            self.assertEqual(value, image_id)

    @mock.patch("stacker.lookups.handlers.ami.get_session",
                return_value=SessionStub(client))
    def test_basic_lookup_multiple_images(self, mock_client):
        image_id = "ami-fffccc111"
        self.stubber.add_response(
            "describe_images",
            {
                "Images": [
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-13T01:17:44.000Z",
                        "State": "available",
                        "ImageId": "ami-fffccc110",
                        "Name": "Fake Image 1",
                        "VirtualizationType": "hvm",
                    },
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-14T01:17:44.000Z",
                        "State": "available",
                        "ImageId": image_id,
                        "Name": "Fake Image 2",
                        "VirtualizationType": "hvm",
                    },
                ]
            }
        )

        with self.stubber:
            value = handler(
                value="owners:self name_regex:Fake\sImage\s\d",
                provider=self.provider
            )
            self.assertEqual(value, image_id)

    @mock.patch("stacker.lookups.handlers.ami.get_session",
                return_value=SessionStub(client))
    def test_basic_lookup_multiple_images_name_match(self, mock_client):
        image_id = "ami-fffccc111"
        self.stubber.add_response(
            "describe_images",
            {
                "Images": [
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-13T01:17:44.000Z",
                        "State": "available",
                        "ImageId": "ami-fffccc110",
                        "Name": "Fa---ke Image 1",
                        "VirtualizationType": "hvm",
                    },
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-14T01:17:44.000Z",
                        "State": "available",
                        "ImageId": image_id,
                        "Name": "Fake Image 2",
                        "VirtualizationType": "hvm",
                    },
                ]
            }
        )

        with self.stubber:
            value = handler(
                value="owners:self name_regex:Fake\sImage\s\d",
                provider=self.provider
            )
            self.assertEqual(value, image_id)

    @mock.patch("stacker.lookups.handlers.ami.get_session",
                return_value=SessionStub(client))
    def test_basic_lookup_no_matching_images(self, mock_client):
        self.stubber.add_response(
            "describe_images",
            {
                "Images": []
            }
        )

        with self.stubber:
            with self.assertRaises(ImageNotFound):
                handler(
                    value="owners:self name_regex:Fake\sImage\s\d",
                    provider=self.provider
                )

    @mock.patch("stacker.lookups.handlers.ami.get_session",
                return_value=SessionStub(client))
    def test_basic_lookup_no_matching_images_from_name(self, mock_client):
        image_id = "ami-fffccc111"
        self.stubber.add_response(
            "describe_images",
            {
                "Images": [
                    {
                        "OwnerId": "897883143566",
                        "Architecture": "x86_64",
                        "CreationDate": "2011-02-13T01:17:44.000Z",
                        "State": "available",
                        "ImageId": image_id,
                        "Name": "Fake Image 1",
                        "VirtualizationType": "hvm",
                    }
                ]
            }
        )

        with self.stubber:
            with self.assertRaises(ImageNotFound):
                handler(
                    value="owners:self name_regex:MyImage\s\d",
                    provider=self.provider
                )
