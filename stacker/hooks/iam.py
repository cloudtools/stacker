import logging

logger = logging.getLogger(__name__)

from aws_helper.connection import ConnectionManager

from awacs.aws import Statement, Allow, Policy
from awacs import ecs


def create_ecs_service_role(region, namespace, mappings, parameters,
                            **kwargs):
    """ Used to create the ecsServieRole, which has to be named exactly that
    currently, so cannot be created via CloudFormation. See:

    http://docs.aws.amazon.com/AmazonECS/latest/developerguide/IAM_policies.html#service_IAM_role
    """
    conn = ConnectionManager(region).iam
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
