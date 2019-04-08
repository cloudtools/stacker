from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str

import pytest
from botocore.stub import Stubber

from stacker.lookups.handlers.ssmstore import SsmstoreLookup
from ...factories import mock_context, mock_provider, mock_boto3_client

REGION = 'us-east-1'
ALT_REGION = 'us-east-2'


@pytest.fixture
def context():
    return mock_context()


@pytest.fixture(params=[dict(region=REGION)])
def provider(request):
    return mock_provider(**request.param)


@pytest.fixture(params=[dict(region=REGION)])
def ssm(request):
    client, mock = mock_boto3_client("ssm", **request.param)
    with mock:
        yield client


@pytest.fixture
def ssm_stubber(ssm):
    with Stubber(ssm) as stubber:
        yield stubber


get_parameters_response = {
    'Parameters': [
        {
            'Name': 'ssmkey',
            'Type': 'String',
            'Value': 'ssmvalue'
        }
    ],
    'InvalidParameters': [
        'invalidssmparam'
    ]
}

invalid_get_parameters_response = {
    'InvalidParameters': [
        'ssmkey'
    ]
}

expected_params = {
    'Names': ['ssmkey'],
    'WithDecryption': True
}

ssmkey = "ssmkey"
ssmvalue = "ssmvalue"


def test_ssmstore_handler(ssm_stubber, context, provider):
    ssm_stubber.add_response('get_parameters',
                             get_parameters_response,
                             expected_params)

    value = SsmstoreLookup.handle(ssmkey, context, provider)
    assert value == ssmvalue
    assert isinstance(value, str)


def test_ssmstore_invalid_value_handler(ssm_stubber, context, provider):
    ssm_stubber.add_response('get_parameters',
                             invalid_get_parameters_response,
                             expected_params)

    with pytest.raises(ValueError):
        SsmstoreLookup.handle(ssmkey, context, provider)


@pytest.mark.parametrize("ssm", [dict(region=ALT_REGION)], indirect=True)
def test_ssmstore_handler_with_region(ssm_stubber, context, provider):
    ssm_stubber.add_response('get_parameters',
                             get_parameters_response,
                             expected_params)
    temp_value = '%s@%s' % (ALT_REGION, ssmkey)

    value = SsmstoreLookup.handle(temp_value, context, provider)
    assert value == ssmvalue
