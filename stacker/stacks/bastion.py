# Bastion Stack
#
# This stack configures our bastion host(s).
# http://en.wikipedia.org/wiki/Bastion_host
#
# These hosts are the only SSH entrypoint into the VPC. To SSH to a host inside
# the VPC you must first SSH to a bastion host, and then SSH from that host to
# another inside the VPC.

from troposphere import Ref, ec2, autoscaling, Parameter, FindInMap
from troposphere.autoscaling import Tag as ASTag

from ..stack import StackTemplateBase

CLUSTER_SG_NAME = "BastionSecurityGroup"


class Bastion(StackTemplateBase):
    def create_parameters(self):
        t = self.template
        t.add_parameter(
            Parameter("VpcId",
                      Type="String",
                      Description="Vpc Id"))
        t.add_parameter(
            Parameter("DefaultSG",
                      Type="String",
                      Description="Top level security group."))
        t.add_parameter(
            Parameter("PublicSubnets",
                      Type="CommaDelimitedList",
                      Description="Subnets to deploy public instances in."))
        t.add_parameter(
            Parameter("PrivateSubnets",
                      Type="CommaDelimitedList",
                      Description="Subnets to deploy private instances in."))
        t.add_parameter(
            Parameter("AvailabilityZones",
                      Type="CommaDelimitedList",
                      Description="Availability Zones to deploy public "
                                  "instances in."))
        t.add_parameter(
            Parameter("OfficeIP",
                      Type="String",
                      Description="IP Allowed to connect to bastion hosts."))
        t.add_parameter(
            Parameter("InstanceType",
                      Type="String",
                      Description="Bastion AWS Instance Type"))
        t.add_parameter(
            Parameter("MinSize",
                      Type="String",
                      Description="Minimum # of bastion instances."))
        t.add_parameter(
            Parameter("MaxSize",
                      Type="String",
                      Description="Maximum # of bastion instances."))
        t.add_parameter(
            Parameter("SshKeyName",
                      Type="AWS::EC2::KeyPair::KeyName"))

    def create_security_groups(self):
        t = self.template
        cluster_rules = []
        cluster_rules.append(
            ec2.SecurityGroupRule(IpProtocol='tcp',
                                  FromPort=22, ToPort=22,
                                  CidrIp=Ref('OfficeIP')))
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
                ImageId=FindInMap('AmiMap', Ref("AWS::Region"), 'bastion'),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
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

    def create_template(self):
        self.create_parameters()
        self.create_security_groups()
        self.create_autoscaling_group()
