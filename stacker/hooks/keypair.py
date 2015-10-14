import logging
import os

from boto.ec2 import connect_to_region

from . import utils

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
    create_or_upload = raw_input(
        'import or create keypair "%s"? (import/create/Cancel) ' % (
            keypair_name,
        ),
    )
    if create_or_upload == 'import':
        path = raw_input('path to keypair file: ')
        full_path = utils.full_path(path)
        if not os.path.exists(full_path):
            logger.error('Failed to find keypair at path: %s', full_path)
            return False

        with open(full_path) as read_file:
            contents = read_file.read()

        keypair = connection.import_key_pair(keypair_name, contents)
        logger.info(message, keypair.name, keypair.fingerprint, 'imported')
        return True
    elif create_or_upload == 'create':
        path = raw_input('directory to save keyfile: ')
        full_path = utils.full_path(path)
        if not os.path.exists(full_path) and not os.path.isdir(full_path):
            logger.error('"%s" is not a valid directory', full_path)
            return False

        keypair = connection.create_key_pair(keypair_name)
        logger.info(message, keypair.name, keypair.fingerprint, 'created')
        return keypair.save(full_path)
    else:
        logger.warning('no action to find keypair, failing')
        return False
