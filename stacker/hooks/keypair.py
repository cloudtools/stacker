import logging
import os

from stacker.session_cache import get_session

from . import utils

logger = logging.getLogger(__name__)


def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return lst[i]
    return False


def ensure_keypair_exists(provider, context, **kwargs):
    """Ensure a specific keypair exists within AWS.

    If the key doesn't exist, upload it.

    Args:
        provider (:class:`stacker.providers.base.BaseProvider`): provider
            instance
        context (:class:`stacker.context.Context`): context instance

    Returns: boolean for whether or not the hook succeeded.

    """
    session = get_session(provider.region)
    client = session.client("ec2")
    keypair_name = kwargs.get("keypair")
    resp = client.describe_key_pairs()
    keypair = find(resp["KeyPairs"], "KeyName", keypair_name)
    message = "keypair: %s (%s) %s"
    if keypair:
        logger.info(message,
                    keypair["KeyName"],
                    keypair["KeyFingerprint"],
                    "exists")
        return {
            "status": "exists",
            "key_name": keypair["KeyName"],
            "fingerprint": keypair["KeyFingerprint"],
        }

    logger.info("keypair: \"%s\" not found", keypair_name)
    create_or_upload = raw_input(
        "import or create keypair \"%s\"? (import/create/Cancel) " % (
            keypair_name,
        ),
    )
    if create_or_upload == "import":
        path = raw_input("path to keypair file: ")
        full_path = utils.full_path(path)
        if not os.path.exists(full_path):
            logger.error("Failed to find keypair at path: %s", full_path)
            return False

        with open(full_path) as read_file:
            contents = read_file.read()

        keypair = client.import_key_pair(KeyName=keypair_name,
                                         PublicKeyMaterial=contents)
        logger.info(message,
                    keypair["KeyName"],
                    keypair["KeyFingerprint"],
                    "imported")
        return {
            "status": "imported",
            "key_name": keypair["KeyName"],
            "fingerprint": keypair["KeyFingerprint"],
            "file_path": full_path,
        }
    elif create_or_upload == "create":
        path = raw_input("directory to save keyfile: ")
        full_path = utils.full_path(path)
        if not os.path.exists(full_path) and not os.path.isdir(full_path):
            logger.error("\"%s\" is not a valid directory", full_path)
            return False

        file_name = "{0}.pem".format(keypair_name)
        if os.path.isfile(os.path.join(full_path, file_name)):
            # This mimics the old boto2 keypair.save error
            logger.error("\"%s\" already exists in \"%s\" directory",
                         file_name,
                         full_path)
            return False

        keypair = client.create_key_pair(KeyName=keypair_name)
        logger.info(message,
                    keypair["KeyName"],
                    keypair["KeyFingerprint"],
                    "created")
        with open(os.path.join(full_path, file_name), "w") as f:
            f.write(keypair["KeyMaterial"])

        return {
            "status": "created",
            "key_name": keypair["KeyName"],
            "fingerprint": keypair["KeyFingerprint"],
            "file_path": os.path.join(full_path, file_name)
        }
    else:
        logger.warning("no action to find keypair, failing")
        return False
