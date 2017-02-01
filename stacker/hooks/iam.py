import copy
import logging

from stacker.session_cache import get_session
from botocore.exceptions import ClientError

from awacs.aws import Statement, Allow, Policy
from awacs import ecs
from awacs.helpers.trust import get_ecs_assumerole_policy

from . import utils

logger = logging.getLogger(__name__)


def create_ecs_service_role(provider, context, **kwargs):
    """Used to create the ecsServieRole, which has to be named exactly that
    currently, so cannot be created via CloudFormation. See:

    http://docs.aws.amazon.com/AmazonECS/latest/developerguide/IAM_policies.html#service_IAM_role

    Args:
        provider (:class:`stacker.providers.base.BaseProvider`): provider
            instance
        context (:class:`stacker.context.Context`): context instance

    Returns: boolean for whether or not the hook succeeded.

    """
    role_name = kwargs.get("role_name", "ecsServiceRole")
    client = get_session(provider.region).client('iam')

    try:
        client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=get_ecs_assumerole_policy().to_json()
        )
    except ClientError as e:
        if "already exists" in e.message:
            pass
        else:
            raise

    policy = Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[ecs.CreateCluster, ecs.DeregisterContainerInstance,
                        ecs.DiscoverPollEndpoint, ecs.Poll,
                        ecs.Action("Submit*")]
            )
        ])
    client.put_role_policy(
        RoleName=role_name,
        PolicyName="AmazonEC2ContainerServiceRolePolicy",
        PolicyDocument=policy.to_json()
    )
    return True


def _get_cert_arn_from_response(response):
    result = copy.deepcopy(response)
    # GET response returns this extra key
    if "ServerCertificate" in response:
        result = response["ServerCertificate"]
    return result["ServerCertificateMetadata"]["Arn"]


def get_cert_contents(kwargs):
    """Builds parameters with server cert file contents.

    Args:
        kwargs(dict): The keyword args passed to ensure_server_cert_exists,
            optionally containing the paths to the cert, key and chain files.

    Returns:
        dict: A dictionary containing the appropriate parameters to supply to
            upload_server_certificate. An empty dictionary if there is a
            problem.
    """
    paths = {
        "certificate": kwargs.get("path_to_certificate"),
        "private_key": kwargs.get("path_to_private_key"),
        "chain": kwargs.get("path_to_chain"),
    }

    for key, value in paths.iteritems():
        if value is not None:
            continue

        path = raw_input("Path to %s (skip): " % (key,))
        if path == "skip" or not path.strip():
            continue

        paths[key] = path

    parameters = {
        "ServerCertificateName": kwargs.get("cert_name"),
    }

    for key, path in paths.iteritems():
        if not path:
            continue

        # Allow passing of file like object for tests
        try:
            contents = path.read()
        except AttributeError:
            with open(utils.full_path(path)) as read_file:
                contents = read_file.read()

        if key == "certificate":
            parameters["CertificateBody"] = contents
        elif key == "private_key":
            parameters["PrivateKey"] = contents
        elif key == "chain":
            parameters["CertificateChain"] = contents

    return parameters


def ensure_server_cert_exists(provider, context, **kwargs):
    client = get_session(provider.region).client('iam')
    cert_name = kwargs["cert_name"]
    status = "unknown"
    try:
        response = client.get_server_certificate(
            ServerCertificateName=cert_name
        )
        cert_arn = _get_cert_arn_from_response(response)
        status = "exists"
        logger.info("certificate exists: %s (%s)", cert_name, cert_arn)
    except ClientError:
        if kwargs.get("prompt", True):
            upload = raw_input(
                "Certificate '%s' wasn't found. Upload it now? (yes/no) " % (
                    cert_name,
                )
            )
            if upload != "yes":
                return False

        parameters = get_cert_contents(kwargs)
        if not parameters:
            return False
        response = client.upload_server_certificate(**parameters)
        cert_arn = _get_cert_arn_from_response(response)
        status = "uploaded"
        logger.info(
            "uploaded certificate: %s (%s)",
            cert_name,
            cert_arn,
        )

    return {
        "status": status,
        "cert_name": cert_name,
        "cert_arn": cert_arn,
    }
