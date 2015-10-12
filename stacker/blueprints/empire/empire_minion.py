import logging
import copy

logger = logging.getLogger(__name__)

from troposphere import Ref, Output, GetAtt, Tags, FindInMap, If, Equals
from troposphere import ec2, autoscaling, ecs
from troposphere.autoscaling import Tag as ASTag
from troposphere.iam import Role, InstanceProfile, Policy

from awacs.helpers.trust import get_default_assumerole_policy

from .empire_base import EmpireBase

from .policies import ecs_agent_policy, logstream_policy

CLUSTER_SG_NAME = "EmpireMinionSecurityGroup"


class EmpireMinion(EmpireBase):
    PARAMETERS = {
        "VpcId": {
            "type": "AWS::EC2::VPC::Id", "description": "Vpc Id"},
        "DefaultSG": {
            "type": "AWS::EC2::SecurityGroup::Id",
            "description": "Top level security group."},
        "PrivateSubnets": {
            "type": "List<AWS::EC2::Subnet::Id>",
            "description": "Subnets to deploy private instances in."},
        "AvailabilityZones": {
            "type": "CommaDelimitedList",
            "description": "Availability Zones to deploy instances in."},
        "InstanceType": {
            "type": "String",
            "description": "Empire AWS Instance Type",
            "default": "c4.2xlarge"},
        "MinSize": {
            "type": "Number",
            "description": "Minimum # of empire minion instances.",
            "default": "3"},
        "MaxSize": {
            "type": "Number",
            "description": "Maximum # of empire minion instances.",
            "default": "20"},
        "SshKeyName": {
            "type": "AWS::EC2::KeyPair::KeyName"},
        "ImageName": {
            "type": "String",
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "NAT"},
        "DockerVolumeSize": {
            "type": "Number",
            "description": "Size, in GB, of the EBS volume where docker will "
                           "store its images and containers.",
            "default": "50"},
        "SwapVolumeSize": {
            "type": "Number",
            "description": "Size, in GB, of the EBS volume that will be "
                           "turned into a swap volume.",
            "default": "16"},
        "DockerRegistry": {
            "type": "String",
            "description": "Optional docker registry where private images "
                           "are located.",
            "default": "https://index.docker.io/v1/"},
        "DockerRegistryUser": {
            "type": "String",
            "description": "User for authentication with docker registry."},
        "DockerRegistryPassword": {
            "type": "String",
            "no_echo": True,
            "description": "Password for authentication with docker "
                           "registry."},
        "DockerRegistryEmail": {
            "type": "String",
            "description": "Email for authentication with docker registry."},
        "DisableStreamingLogs": {
            "type": "String",
            "description": "Disables streaming logging if set to anything."
                           "Note: Without this Empire creates a kinesis "
                           "stream per app that you deploy in Empire.",
            "default": "",
        },
    }

    def create_conditions(self):
        t = self.template
        t.add_condition(
            "EnableStreamingLogs",
            Equals(Ref("DisableStreamingLogs"), ""))

    def create_security_groups(self):
        t = self.template
        t.add_resource(
            ec2.SecurityGroup(CLUSTER_SG_NAME,
                              GroupDescription='EmpireMinionSecurityGroup',
                              VpcId=Ref("VpcId")))
        t.add_output(
            Output('EmpireMinionSG', Value=Ref(CLUSTER_SG_NAME)))
        # Allow all ports within cluster
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireMinionAllTCPAccess",
                IpProtocol='-1', FromPort='-1', ToPort='-1',
                SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                GroupId=Ref(CLUSTER_SG_NAME)))

        # Application ELB Security Groups
        # Internal
        for elb in ('public', 'private'):
            group_name = "Empire%sAppELBSG" % elb.capitalize()
            t.add_resource(
                ec2.SecurityGroup(
                    group_name,
                    GroupDescription=group_name,
                    VpcId=Ref("VpcId"),
                    Tags=Tags(Name='%s-app-elb-sg' % elb)))
            t.add_output(
                Output("%sEmpireAppELBSG" % elb.capitalize(),
                       Value=Ref(group_name)))

            # Allow ELB to talk to cluster on 9000-10000
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "Empire%sAppPort9000To10000" % elb.capitalize(),
                    IpProtocol="tcp", FromPort=9000, ToPort=10000,
                    SourceSecurityGroupId=Ref(group_name),
                    GroupId=Ref(CLUSTER_SG_NAME)))

            # Allow anything to talk to the ELB
            # If internal only internal hosts will be able to talk to
            # the elb
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "Empire%sELBAllow80" % elb.capitalize(),
                    IpProtocol="tcp", FromPort=80, ToPort=80,
                    CidrIp="0.0.0.0/0",
                    GroupId=Ref(group_name)))
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "Empire%sELBAllow443" % elb.capitalize(),
                    IpProtocol="tcp", FromPort=443, ToPort=443,
                    CidrIp="0.0.0.0/0",
                    GroupId=Ref(group_name)))

    def build_block_device(self):
        docker_volume = autoscaling.BlockDeviceMapping(
            DeviceName="/dev/sdh",
            Ebs=autoscaling.EBSBlockDevice(
                DeleteOnTermination=True,
                VolumeSize=Ref("DockerVolumeSize")))
        swap_volume = autoscaling.BlockDeviceMapping(
            DeviceName="/dev/sdi",
            Ebs=autoscaling.EBSBlockDevice(
                DeleteOnTermination=True,
                VolumeSize=Ref("SwapVolumeSize")))

        return [docker_volume, swap_volume]

    def generate_iam_policies(self):
        ns = self.context.namespace
        base_policies = [
            Policy(
                PolicyName="%s-ecs-agent" % ns,
                PolicyDocument=ecs_agent_policy()),
        ]
        with_logging = copy.deepcopy(base_policies)
        with_logging.append(
            Policy(
                PolicyName="%s-kinesis-logging" % ns,
                PolicyDocument=logstream_policy()
            )
        )
        policies = If("EnableStreamingLogs", with_logging, base_policies)
        return policies

    def create_iam_profile(self):
        t = self.template
        ec2_role_policy = get_default_assumerole_policy()
        t.add_resource(
            Role(
                "EmpireMinionRole",
                AssumeRolePolicyDocument=ec2_role_policy,
                Path="/",
                Policies=self.generate_iam_policies()))
        t.add_resource(
            InstanceProfile(
                "EmpireMinionProfile",
                Path="/",
                Roles=[Ref("EmpireMinionRole")]))

    def create_ecs_cluster(self):
        t = self.template
        t.add_resource(ecs.Cluster("EmpireMinionCluster"))
        t.add_output(
            Output("MinionECSCluster", Value=Ref("EmpireMinionCluster")))

    def generate_seed_contents(self):
        seed = [
            "EMPIRE_HOSTGROUP=minion\n",
            "ECS_CLUSTER=", Ref("EmpireMinionCluster"), "\n",
            "DOCKER_REGISTRY=", Ref("DockerRegistry"), "\n",
            "DOCKER_USER=", Ref("DockerRegistryUser"), "\n",
            "DOCKER_PASS=", Ref("DockerRegistryPassword"), "\n",
            "DOCKER_EMAIL=", Ref("DockerRegistryEmail"), "\n",
            "ENABLE_STREAMING_LOGS=", If("EnableStreamingLogs",
                                         "true", "false"), "\n"
            ]
        return seed

    def create_autoscaling_group(self):
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                'EmpireMinionLaunchConfig',
                IamInstanceProfile=GetAtt("EmpireMinionProfile",
                                          "Arn"),
                ImageId=FindInMap('AmiMap',
                                  Ref("AWS::Region"),
                                  Ref("ImageName")),
                BlockDeviceMappings=self.build_block_device(),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
                UserData=self.generate_user_data(),
                SecurityGroups=[Ref("DefaultSG"), Ref(CLUSTER_SG_NAME)]))
        t.add_resource(
            autoscaling.AutoScalingGroup(
                'EmpireMinionAutoscalingGroup',
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref("EmpireMinionLaunchConfig"),
                MinSize=Ref("MinSize"),
                MaxSize=Ref("MaxSize"),
                VPCZoneIdentifier=Ref("PrivateSubnets"),
                Tags=[ASTag('Name', 'empire_minion', True)]))
