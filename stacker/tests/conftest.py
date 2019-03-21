from __future__ import absolute_import, division, print_function

import logging
import os

import pytest
import py.path

logger = logging.getLogger(__name__)


@pytest.fixture(scope='session', autouse=True)
def aws_credentials():
    # Handle change in https://github.com/spulec/moto/issues/1924
    # Ensure AWS SDK finds some (bogus) credentials in the environment and
    # doesn't try to use other providers.
    overrides = {
        'AWS_ACCESS_KEY_ID': 'testing',
        'AWS_SECRET_ACCESS_KEY': 'testing',
        'AWS_DEFAULT_REGION': 'us-east-1'
    }
    saved_env = {}
    for key, value in overrides.items():
        logger.info('Overriding env var: {}={}'.format(key, value))
        saved_env[key] = os.environ.get(key, None)
        os.environ[key] = value

    yield

    for key, value in saved_env.items():
        logger.info('Restoring saved env var: {}={}'.format(key, value))
        if value is None:
            del os.environ[key]
        else:
            os.environ[key] = value

    saved_env.clear()


@pytest.fixture(scope="package")
def stacker_fixture_dir():
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        'fixtures')
    return py.path.local(path)
