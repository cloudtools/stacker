from base64 import b64encode
import logging
import os

from boto.ec2 import connect_to_region

logger = logging.getLogger(__name__)


def ensure_keypair_exists(region, namespace, mappings, parameters, **kwargs):
    connection = connect_to_region(region)
    keypair_name = kwargs.get('keypair', parameters.get('SshKeyName'))
    keypair = connection.get_key_pair(keypair_name)
    message = 'keypair: %s (%s) %s'
    if keypair:
        logger.info(message, keypair.name, keypair.fingerprint, 'exists')
        return True

    logger.info('keypair: "%s" not found', keypair_name)
    upload = raw_input(
        'would you like to import "%s" keypair now? (yes/no) ' % (
            keypair_name,
        ),
    )
    if upload == 'yes':
        path = raw_input('path to keypair file: ')
        full_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(full_path):
            logger.error('Failed to find keypair at path: %s', full_path)
            return False

        with open(full_path) as read_file:
            contents = read_file.read()

        keypair = connection.import_key_pair(keypair_name,
                                             b64encode(contents))
        logger.info(message, keypair.name, keypair.fingerprint, 'imported')
        return True
    else:
        logger.warning('keypair must manually be imported')
        return False
