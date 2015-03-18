from troposphere import Ref, FindInMap
from troposphere import ec2, autoscaling
from troposphere.autoscaling import Tag as ASTag

from .base import Blueprint

CLUSTER_SG_NAME = "%sSG"


class AutoscalingGroup(Blueprint):
    PARAMETERS = {
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
        'DefaultSG': {'type': 'AWS::EC2::SecurityGroup::Id',
                      'description': 'Top level security group.'},
        'PrivateSubnets': {'type': 'List<AWS::EC2::Subnet::Id>',
                           'description': 'Subnets to deploy private '
                                          'instances in.'},
        'AvailabilityZones': {'type': 'CommaDelimitedList',
                              'description': 'Availability Zones to deploy '
                                             'instances in.'},
        'InstanceType': {'type': 'String',
                         'description': 'EC2 Instance Type',
                         'default': 'm3.medium'},
        'MinSize': {'type': 'Number',
                    'description': 'Minimum # of instances.',
                    'default': '1'},
        'MaxSize': {'type': 'Number',
                    'description': 'Maximum # of instances.',
                    'default': '5'},
        'SshKeyName': {'type': 'AWS::EC2::KeyPair::KeyName'},
        'ImageName': {
            'type': 'String',
            'description': 'The image name to use from the AMIMap (usually '
                           'found in the config file.)'},
    }

    def create_security_groups(self):
        t = self.template
        t.add_resource(
            ec2.SecurityGroup(CLUSTER_SG_NAME % self.name,
                              GroupDescription=CLUSTER_SG_NAME % self.name,
                              VpcId=Ref("VpcId")))
        # Add SG rules here

    def create_autoscaling_group(self):
        name = "%sASG" % self.name
        sg_name = CLUSTER_SG_NAME % self.name
        launch_config = "%sLaunchConfig" % name
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                launch_config,
                ImageId=FindInMap('AmiMap', Ref("AWS::Region"),
                                  Ref('ImageName')),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
                SecurityGroups=[Ref("DefaultSG"), Ref(sg_name)]))
        t.add_resource(
            autoscaling.AutoScalingGroup(
                '%sAutoScalingGroup' % name,
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref(launch_config),
                MinSize=Ref("MinSize"),
                MaxSize=Ref("MaxSize"),
                VPCZoneIdentifier=Ref("PrivateSubnets"),
                Tags=[ASTag('Name', self.name, True)]))

    def create_template(self):
        self.create_security_groups()
        self.create_autoscaling_group()
