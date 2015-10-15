import logging
import os

logger = logging.getLogger(__name__)

from boto.exception import BotoServerError
from boto.iam import connect_to_region

from awacs.aws import Statement, Allow, Policy
from awacs import ecs

from . import utils


def create_ecs_service_role(region, namespace, mappings, parameters,
                            **kwargs):
    """Used to create the ecsServieRole, which has to be named exactly that
    currently, so cannot be created via CloudFormation. See:

    http://docs.aws.amazon.com/AmazonECS/latest/developerguide/IAM_policies.html#service_IAM_role

    """
    conn = connect_to_region(region)
    policy = Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[ecs.CreateCluster, ecs.DeregisterContainerInstance,
                        ecs.DiscoverPollEndpoint, ecs.Poll,
                        ecs.ECSAction("Submit*")]
            )
        ])
    conn.put_role_policy("ecsServiceRole", "AmazonEC2ContainerServiceRole",
                         policy.to_json())
    return True


def _get_cert_arn_from_response(prefix, response):
    response_key = '%s_response' % (prefix,)
    result_key = '%s_result' % (prefix,)
    result = response[response_key][
        result_key
    ]
    # GET response returns this extra key
    if 'server_certificate' in result:
        result = result['server_certificate']
    return result['server_certificate_metadata']['arn']


def ensure_server_cert_exists(region, namespace, mappings, parameters, **kwargs):
    conn = connect_to_region(region)
    cert_name = kwargs['cert_name']
    try:
        response = conn.get_server_certificate(cert_name)
        cert_arn = _get_cert_arn_from_response(
            'get_server_certificate',
            response,
        )
        logger.info('certificate exists: %s (%s)', cert_name, cert_arn)
    except BotoServerError:
        upload = raw_input(
            'Certificate "%s" wasn\'t found. Upload it now? (yes/no) ' % (
                cert_name,
            )
        )
        if upload != 'yes':
            return False

        paths = {
            'certificate': kwargs.get('path_to_certificate'),
            'private_key': kwargs.get('path_to_private_key'),
            'chain': kwargs.get('path_to_chain'),
        }

        for key, value in paths.iteritems():
            if value is not None:
                continue

            path = raw_input('Path to %s (skip): ' % (key,))
            if path == 'skip' or not path.strip():
                continue

            full_path = utils.full_path(path)
            if not os.path.exists(full_path):
                logger.error('%s path "%s" does not exist', key, full_path)
                return False
            paths[key] = full_path

        parameters = {
            'cert_name': cert_name,
        }
        for key, path in paths.iteritems():
            if not path:
                continue

            with open(path) as read_file:
                contents = read_file.read()

            if key == 'certificate':
                parameters['cert_body'] = contents
            elif key == 'private_key':
                parameters['private_key'] = contents
            elif key == 'chain':
                parameters['cert_chain'] = contents

        response = conn.upload_server_cert(**parameters)
        cert_arn = _get_cert_arn_from_response(
            'upload_server_certificate',
            response,
        )
        logger.info(
            'uploaded certificate: %s (%s)',
            cert_name,
            cert_arn,
        )

    return True
