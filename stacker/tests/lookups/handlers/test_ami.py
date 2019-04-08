from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from botocore.stub import Stubber
import pytest

from stacker.lookups.handlers.ami import AmiLookup, ImageNotFound
from ...factories import mock_boto3_client, mock_context, mock_provider


REGION = "us-east-1"
ALT_REGION = "us-east-2"


@pytest.fixture
def context():
    return mock_context()


@pytest.fixture(params=[dict(region=REGION)])
def provider(request):
    return mock_provider(**request.param)


@pytest.fixture(params=[dict(region=REGION)])
def ec2(request):
    client, mock = mock_boto3_client("ec2", **request.param)
    with mock:
        yield client


@pytest.fixture
def ec2_stubber(ec2):
    with Stubber(ec2) as stubber:
        yield stubber


def test_basic_lookup_single_image(ec2_stubber, context, provider):
    image_id = "ami-fffccc111"
    ec2_stubber.add_response(
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

    value = AmiLookup.handle(
        value=r"owners:self name_regex:Fake\sImage\s\d",
        context=context,
        provider=provider
    )
    assert value == image_id


@pytest.mark.parametrize("ec2", [dict(region=ALT_REGION)], indirect=True)
def test_basic_lookup_with_region(ec2_stubber, context, provider):
    image_id = "ami-fffccc111"
    ec2_stubber.add_response(
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

    key = r"{}@owners:self name_regex:Fake\sImage\s\d".format(ALT_REGION)
    value = AmiLookup.handle(
        value=key,
        context=context,
        provider=provider
    )
    assert value == image_id


def test_basic_lookup_multiple_images(ec2_stubber, context, provider):
    image_id = "ami-fffccc111"
    ec2_stubber.add_response(
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

    value = AmiLookup.handle(
        value=r"owners:self name_regex:Fake\sImage\s\d",
        context=context,
        provider=provider
    )
    assert value == image_id


def test_basic_lookup_multiple_images_name_match(ec2_stubber, context,
                                                 provider):
    image_id = "ami-fffccc111"
    ec2_stubber.add_response(
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

    value = AmiLookup.handle(
        value=r"owners:self name_regex:Fake\sImage\s\d",
        context=context,
        provider=provider
    )
    assert value == image_id


def test_basic_lookup_no_matching_images(ec2_stubber, context, provider):
    ec2_stubber.add_response(
        "describe_images",
        {
            "Images": []
        }
    )

    with pytest.raises(ImageNotFound):
        AmiLookup.handle(
            value=r"owners:self name_regex:Fake\sImage\s\d",
            context=context,
            provider=provider
        )


def test_basic_lookup_no_matching_images_from_name(ec2_stubber, context,
                                                   provider):
    image_id = "ami-fffccc111"
    ec2_stubber.add_response(
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

    with pytest.raises(ImageNotFound):
        AmiLookup.handle(
            value=r"owners:self name_regex:MyImage\s\d",
            context=context,
            provider=provider
        )
