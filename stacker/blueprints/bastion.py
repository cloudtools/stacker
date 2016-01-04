# Bastion Stack
#
# This stack configures our bastion host(s).
# http://en.wikipedia.org/wiki/Bastion_host
#
# These hosts are the only SSH entrypoint into the VPC. To SSH to a host inside
# the VPC you must first SSH to a bastion host, and then SSH from that host to
# another inside the VPC.

import warnings

warnings.warn("The included blueprints are deprecated. You should install "
              "the `stacker_blueprints` module instead.",
              DeprecationWarning)

from troposphere import Ref, ec2, autoscaling, FindInMap
from troposphere.autoscaling import Tag as ASTag

from .base import Blueprint

CLUSTER_SG_NAME = "BastionSecurityGroup"


class Bastion(Blueprint):
    PARAMETERS = {
        "VpcId": {"type": "AWS::EC2::VPC::Id", "description": "Vpc Id"},
        "DefaultSG": {"type": "AWS::EC2::SecurityGroup::Id",
                      "description": "Top level security group."},
        "PublicSubnets": {"type": "List<AWS::EC2::Subnet::Id>",
                          "description": "Subnets to deploy public "
                                         "instances in."},
        "PrivateSubnets": {"type": "List<AWS::EC2::Subnet::Id>",
                           "description": "Subnets to deploy private "
                                          "instances in."},
        "AvailabilityZones": {"type": "CommaDelimitedList",
                              "description": "Availability Zones to deploy "
                                             "instances in."},
        "InstanceType": {"type": "String",
                         "description": "EC2 Instance Type",
                         "default": "m3.medium"},
        "MinSize": {"type": "Number",
                    "description": "Minimum # of instances.",
                    "default": "1"},
        "MaxSize": {"type": "Number",
                    "description": "Maximum # of instances.",
                    "default": "5"},
        "SshKeyName": {"type": "AWS::EC2::KeyPair::KeyName"},
        "OfficeNetwork": {
            "type": "String",
            "description": "CIDR block allowed to connect to bastion hosts."},
        "ImageName": {
            "type": "String",
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "bastion"},
    }

    def create_security_groups(self):
        t = self.template
        cluster_rules = []
        cluster_rules.append(
            ec2.SecurityGroupRule(IpProtocol='tcp',
                                  FromPort=22, ToPort=22,
                                  CidrIp=Ref('OfficeNetwork')))
        t.add_resource(
            ec2.SecurityGroup(CLUSTER_SG_NAME,
                              GroupDescription='BastionSecurityGroup',
                              SecurityGroupIngress=cluster_rules,
                              VpcId=Ref("VpcId")))

        # Make it so the bastion hosts can ssh into any other host.
        t.add_resource(
            ec2.SecurityGroupIngress(
                'AllowSSHAnywhere',
                IpProtocol='tcp',
                FromPort=22,
                ToPort=22,
                SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                GroupId=Ref('DefaultSG')))

    def create_autoscaling_group(self):
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                'BastionLaunchConfig',
                AssociatePublicIpAddress=True,
                ImageId=FindInMap(
                    'AmiMap', Ref("AWS::Region"), Ref("ImageName")),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
                UserData=self.generate_user_data(),
                SecurityGroups=[Ref("DefaultSG"), Ref(CLUSTER_SG_NAME)]))
        t.add_resource(
            autoscaling.AutoScalingGroup(
                'BastionAutoscalingGroup',
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref("BastionLaunchConfig"),
                MinSize=Ref("MinSize"),
                MaxSize=Ref("MaxSize"),
                VPCZoneIdentifier=Ref("PublicSubnets"),
                Tags=[ASTag('Name', 'bastion', True)]))

    def generate_user_data(self):
        return ''

    def create_template(self):
        self.create_security_groups()
        self.create_autoscaling_group()
