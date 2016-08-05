import copy
import logging
import os
import os.path

logger = logging.getLogger(__name__)

import boto3
from botocore.exceptions import ClientError

from awacs.aws import Statement, Allow, Policy
from awacs import ecs

from . import utils


def create_ecs_service_role(region, namespace, mappings, parameters,
                            **kwargs):
    """Used to create the ecsServieRole, which has to be named exactly that
    currently, so cannot be created via CloudFormation. See:

    http://docs.aws.amazon.com/AmazonECS/latest/developerguide/IAM_policies.html#service_IAM_role

    """
    client = boto3.client("iam", region_name=region)
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
    client.put_role_policy(
        RoleName="ecsServiceRole",
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


def ensure_server_cert_exists(region, namespace, mappings, parameters,
                              **kwargs):
    client = boto3.client("iam", region_name=region)
    cert_name = kwargs["cert_name"]
    try:
        response = client.get_server_certificate(
            ServerCertificateName=cert_name
        )
        cert_arn = _get_cert_arn_from_response(response)
        logger.info("certificate exists: %s (%s)", cert_name, cert_arn)
    except ClientError:
        upload = raw_input(
            "Certificate '%s' wasn't found. Upload it now? (yes/no) " % (
                cert_name,
            )
        )
        if upload != "yes":
            return False

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

            full_path = utils.full_path(path)
            if not os.path.exists(full_path):
                print "%s path %s does not exist." % (key, full_path)
                logger.error("%s path '%s' does not exist", key, full_path)
                return False
            paths[key] = full_path

        parameters = {
            "ServerCertificateName": cert_name,
        }
        for key, path in paths.iteritems():
            if not path:
                continue

            with open(path) as read_file:
                contents = read_file.read()

            if key == "certificate":
                parameters["CertificateBody"] = contents
            elif key == "private_key":
                parameters["PrivateKey"] = contents
            elif key == "chain":
                parameters["CertificateChain"] = contents

        response = client.upload_server_certificate(**parameters)
        cert_arn = _get_cert_arn_from_response(response)
        logger.info(
            "uploaded certificate: %s (%s)",
            cert_name,
            cert_arn,
        )

    return True
