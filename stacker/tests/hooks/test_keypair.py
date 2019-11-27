from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import sys
from collections import namedtuple
from contextlib import contextmanager

import mock
import pytest

import boto3
from moto import mock_ec2, mock_ssm

from stacker.hooks.keypair import ensure_keypair_exists
from ..factories import mock_context, mock_provider


REGION = "us-east-1"
KEY_PAIR_NAME = "FakeKey"

SSHKey = namedtuple('SSHKey', 'public_key private_key fingerprint')


@pytest.fixture(scope="module")
def ssh_key(stacker_fixture_dir):
    base = stacker_fixture_dir.join('keypair')
    return SSHKey(
        private_key=base.join('id_rsa').read_binary(),
        public_key=base.join('id_rsa.pub').read_binary(),
        fingerprint=base.join('fingerprint').read_text('ascii').strip())


@pytest.fixture
def provider():
    return mock_provider(region=REGION)


@pytest.fixture
def context():
    return mock_context(namespace="fake")


@pytest.fixture(autouse=True)
def ec2(ssh_key):
    # Force moto to generate a deterministic key pair on creation.
    # Can be replaced by something more sensible when
    # https://github.com/spulec/moto/pull/2108 is merged

    key_pair = {'fingerprint': ssh_key.fingerprint,
                'material': ssh_key.private_key.decode('ascii')}
    with mock.patch('moto.ec2.models.random_key_pair', side_effect=[key_pair]):
        with mock_ec2():
            yield


@pytest.fixture(autouse=True)
def ssm():
    with mock_ssm():
        yield


@contextmanager
def mock_input(lines=(), isatty=True):
    with mock.patch('stacker.hooks.keypair.get_raw_input',
                    side_effect=lines) as m:
        with mock.patch.object(sys.stdin, 'isatty', return_value=isatty):
            yield m


def assert_key_present(hook_result, key_name, fingerprint):
    assert hook_result['key_name'] == key_name
    assert hook_result['fingerprint'] == fingerprint

    ec2 = boto3.client('ec2')
    response = ec2.describe_key_pairs(KeyNames=[key_name], DryRun=False)
    key_pairs = response['KeyPairs']

    assert len(key_pairs) == 1
    assert key_pairs[0]['KeyName'] == key_name
    assert key_pairs[0]['KeyFingerprint'] == fingerprint


def test_param_validation(provider, context):
    result = ensure_keypair_exists(provider, context, keypair=KEY_PAIR_NAME,
                                   ssm_parameter_name='test',
                                   public_key_path='test')
    assert result is False


def test_keypair_exists(provider, context):
    ec2 = boto3.client('ec2')
    keypair = ec2.create_key_pair(KeyName=KEY_PAIR_NAME)

    result = ensure_keypair_exists(provider, context, keypair=KEY_PAIR_NAME)
    expected = dict(
        status='exists',
        key_name=KEY_PAIR_NAME,
        fingerprint=keypair['KeyFingerprint'])
    assert result == expected


def test_import_file(tmpdir, provider, context, ssh_key):
    pkey = tmpdir.join("id_rsa.pub")
    pkey.write(ssh_key.public_key)

    result = ensure_keypair_exists(provider, context, keypair=KEY_PAIR_NAME,
                                   public_key_path=str(pkey))
    assert_key_present(result, KEY_PAIR_NAME, ssh_key.fingerprint)
    assert result['status'] == 'imported'


def test_import_bad_key_data(tmpdir, provider, context):
    pkey = tmpdir.join("id_rsa.pub")
    pkey.write('garbage')

    result = ensure_keypair_exists(provider, context, keypair=KEY_PAIR_NAME,
                                   public_key_path=str(pkey))
    assert result is False


@pytest.mark.parametrize('ssm_key_id', ('my-key'))
def test_create_in_ssm(provider, context, ssh_key, ssm_key_id):
    result = ensure_keypair_exists(provider, context, keypair=KEY_PAIR_NAME,
                                   ssm_parameter_name='param',
                                   ssm_key_id=ssm_key_id)

    assert_key_present(result, KEY_PAIR_NAME, ssh_key.fingerprint)
    assert result['status'] == 'created'

    ssm = boto3.client('ssm')
    param = ssm.get_parameter(Name='param', WithDecryption=True)['Parameter']
    assert param['Value'] == ssh_key.private_key.decode('ascii')
    assert param['Type'] == 'SecureString'

    params = ssm.describe_parameters()['Parameters']
    param_details = next(p for p in params if p['Name'] == 'param')
    assert param_details['Description'] == \
        'SSH private key for KeyPair "{}" (generated by Stacker)'.format(
            KEY_PAIR_NAME)
    assert param_details.get('KeyId') == ssm_key_id


def test_interactive_non_terminal_input(capsys, provider, context):
    with mock_input(isatty=False) as input:
        result = ensure_keypair_exists(provider, context,
                                       keypair=KEY_PAIR_NAME)
        input.assert_not_called()
    assert result is False

    output = capsys.readouterr()
    assert len(output.out) == 0
    assert len(output.err) == 0


def test_interactive_retry_cancel(provider, context):
    lines = ['garbage', 'cancel']
    with mock_input(lines) as input:
        result = ensure_keypair_exists(
            provider, context, keypair=KEY_PAIR_NAME)
        assert input.call_count == 2

    assert result is False


def test_interactive_import(tmpdir, provider, context, ssh_key):
    key_file = tmpdir.join("id_rsa.pub")
    key_file.write(ssh_key.public_key)

    lines = ['import', str(key_file)]
    with mock_input(lines):
        result = ensure_keypair_exists(
            provider, context, keypair=KEY_PAIR_NAME)

    assert_key_present(result, KEY_PAIR_NAME, ssh_key.fingerprint)
    assert result['status'] == 'imported'


def test_interactive_create(tmpdir, provider, context, ssh_key):
    key_dir = tmpdir.join('keys')
    key_dir.ensure_dir()
    key_file = key_dir.join('{}.pem'.format(KEY_PAIR_NAME))

    lines = ['create', str(key_dir)]
    with mock_input(lines):
        result = ensure_keypair_exists(
            provider, context, keypair=KEY_PAIR_NAME)

    assert_key_present(result, KEY_PAIR_NAME, ssh_key.fingerprint)
    assert result['status'] == 'created'
    assert key_file.samefile(result['file_path'])
    assert key_file.read_binary() == ssh_key.private_key


def test_interactive_create_bad_dir(tmpdir, provider, context):
    key_dir = tmpdir.join('missing')

    lines = ['create', str(key_dir)]
    with mock_input(lines):
        result = ensure_keypair_exists(
            provider, context, keypair=KEY_PAIR_NAME)

    assert result is False


def test_interactive_create_existing_file(tmpdir, provider, context):
    key_dir = tmpdir.join('keys')
    key_dir.ensure_dir()
    key_file = key_dir.join('{}.pem'.format(KEY_PAIR_NAME))
    key_file.ensure()

    lines = ['create', str(key_dir)]
    with mock_input(lines):
        result = ensure_keypair_exists(
            provider, context, keypair=KEY_PAIR_NAME)

    assert result is False
