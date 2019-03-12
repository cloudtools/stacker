from __future__ import absolute_import, division, print_function

import logging
import os


logger = logging.getLogger(__name__)
_saved_env = {}


def setUpModule():
    # Handle change in  https://github.com/spulec/moto/issues/1924
    # Ensure AWS SDK find some (bogus) credentials in the environment and
    # doesn't try to use other providers
    overrides = {
        'AWS_ACCESS_KEY_ID': 'testing',
        'AWS_SECRET_ACCESS_KEY': 'testing',
        'AWS_DEFAULT_REGION': 'us-east-1'
    }
    for key, value in overrides.items():
        logger.info('Overriding env var: {}={}'.format(key, value))
        _saved_env[key] = os.environ.get(key, None)
        os.environ[key] = value


def tearDownModule():
    for key, value in _saved_env.items():
        logger.info('Restoring saved env var: {}={}'.format(key, value))
        if value is None:
            del os.environ[key]
        else:
            os.environ[key] = value

    _saved_env.clear()
