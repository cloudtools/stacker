from troposphere import Ref, ec2, autoscaling, Parameter, FindInMap
from troposphere.autoscaling import Tag as ASTag

from ..stack import StackTemplateBase

CLUSTER_SG_NAME = "ConsulSecurityGroup"


class ConsulServer(StackTemplateBase):
    PARAMETERS = {
        'VpcId': {'type': 'String', 'description': 'Vpc Id'},
        'DefaultSG': {'type': 'String',
                      'description': 'Top level security group.'},
        'PrivateSubnets': {'type': 'CommaDelimitedList',
                          'description': 'Subnets to deploy private instances '
                                         'in.'},
        'AvailabilityZones': {'type': 'CommaDelimitedList',
                              'description': 'Availability Zones to deploy '
                                             'instances in.'},
        'InstanceType': {'type': 'String',
                         'description': 'Consul AWS Instance Type'},
        'MinSize': {'type': 'String',
                    'description': 'Minimum # of consul instances.'},
        'MaxSize': {'type': 'String',
                    'description': 'Maximum # of consul instances.'},
        'SshKeyName': {'type': 'AWS::EC2::KeyPair::KeyName'}
    }

    def create_parameters(self):
        t = self.template
        for param, attrs in self.PARAMETERS.items():
            t.add_parameter(
                Parameter(param,
                          Type=attrs.get('type'),
                          Description=attrs.get('description', '')))

    def create_security_groups(self):
        t = self.template
        cluster_rules = []
        ports = {
            'udp': [8600],
            'tcp': [8300, 8600]}

        t.add_resource(
            ec2.SecurityGroup(CLUSTER_SG_NAME,
                              GroupDescription='ConsulSecurityGroup',
                              SecurityGroupIngress=cluster_rules,
                              VpcId=Ref("VpcId")))
        for proto in ports:
            for port in ports[proto]:
                t.add_resource(
                    ec2.SecurityGroupIngress(
                        "ConsulServerPort%s%d" % (proto.capitalize(), port),
                        IpProtocol=proto, FromPort=port, ToPort=port,
                        SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                        GroupId=Ref(CLUSTER_SG_NAME)))

    def create_autoscaling_group(self):
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                'ConsulLaunchConfig',
                ImageId=FindInMap('AmiMap', Ref("AWS::Region"), 'consul'),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
                SecurityGroups=[Ref("DefaultSG"), Ref(CLUSTER_SG_NAME)]))
        t.add_resource(
            autoscaling.AutoScalingGroup(
                'ConsulAutoscalingGroup',
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref("ConsulLaunchConfig"),
                MinSize=Ref("MinSize"),
                MaxSize=Ref("MaxSize"),
                VPCZoneIdentifier=Ref("PrivateSubnets"),
                Tags=[ASTag('Name', 'consul', True)]))

    def create_template(self):
        self.create_parameters()
        self.create_security_groups()
        self.create_autoscaling_group()
