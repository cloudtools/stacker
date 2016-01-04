import copy

import warnings

warnings.warn("The included blueprints are deprecated. You should install "
              "the `stacker_blueprints` module instead.",
              DeprecationWarning)

from troposphere import (
    Ref, FindInMap, Not, Equals, And, Condition, Join, ec2, autoscaling,
    If, GetAtt
)
from troposphere import elasticloadbalancing as elb
from troposphere.autoscaling import Tag as ASTag
from troposphere.route53 import RecordSetType

from .base import Blueprint

CLUSTER_SG_NAME = "%sSG"
ELB_SG_NAME = "%sElbSG"
ELB_NAME = "%sLoadBalancer"


class AutoscalingGroup(Blueprint):
    PARAMETERS = {
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
        'DefaultSG': {'type': 'AWS::EC2::SecurityGroup::Id',
                      'description': 'Top level security group.'},
        'BaseDomain': {
            'type': 'String',
            'default': '',
            'description': 'Base domain for the stack.'},
        'PrivateSubnets': {'type': 'List<AWS::EC2::Subnet::Id>',
                           'description': 'Subnets to deploy private '
                                          'instances in.'},
        'PublicSubnets': {'type': 'List<AWS::EC2::Subnet::Id>',
                          'description': 'Subnets to deploy public (elb) '
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
        'ELBHostName': {
            'type': 'String',
            'description': 'A hostname to give to the ELB. If not given '
                           'no ELB will be created.',
            'default': ''},
        'ELBCertName': {
            'type': 'String',
            'description': 'The SSL certificate name to use on the ELB.',
            'default': ''},
    }

    def create_conditions(self):
        self.template.add_condition(
            "CreateELB",
            Not(Equals(Ref("ELBHostName"), "")))
        self.template.add_condition(
            "SetupDNS",
            Not(Equals(Ref("BaseDomain"), "")))
        self.template.add_condition(
            "UseSSL",
            Not(Equals(Ref("ELBCertName"), "")))
        self.template.add_condition(
            "CreateSSLELB",
            And(Condition("CreateELB"), Condition("UseSSL")))
        self.template.add_condition(
            "SetupELBDNS",
            And(Condition("CreateELB"), Condition("SetupDNS")))

    def create_security_groups(self):
        t = self.template
        asg_sg = CLUSTER_SG_NAME % self.name
        elb_sg = ELB_SG_NAME % self.name
        t.add_resource(ec2.SecurityGroup(
            asg_sg,
            GroupDescription=asg_sg,
            VpcId=Ref("VpcId")))
        # ELB Security group, if ELB is used
        t.add_resource(
            ec2.SecurityGroup(
                elb_sg,
                GroupDescription=elb_sg,
                VpcId=Ref("VpcId"),
                Condition="CreateELB"))
        # Add SG rules here
        # Allow ELB to connect to ASG on port 80
        t.add_resource(ec2.SecurityGroupIngress(
            "%sElbToASGPort80" % self.name,
            IpProtocol="tcp", FromPort="80", ToPort="80",
            SourceSecurityGroupId=Ref(elb_sg),
            GroupId=Ref(asg_sg),
            Condition="CreateELB"))
        # Allow Internet to connect to ELB on port 80
        t.add_resource(ec2.SecurityGroupIngress(
            "InternetTo%sElbPort80" % self.name,
            IpProtocol="tcp", FromPort="80", ToPort="80",
            CidrIp="0.0.0.0/0",
            GroupId=Ref(elb_sg),
            Condition="CreateELB"))
        t.add_resource(ec2.SecurityGroupIngress(
            "InternetTo%sElbPort443" % self.name,
            IpProtocol="tcp", FromPort="443", ToPort="443",
            CidrIp="0.0.0.0/0",
            GroupId=Ref(elb_sg),
            Condition="CreateSSLELB"))

    def setup_listeners(self):
        no_ssl = [elb.Listener(
            LoadBalancerPort=80,
            Protocol='HTTP',
            InstancePort=80,
            InstanceProtocol='HTTP'
        )]

        cert_id = Join("", [
            "arn:aws:iam::", Ref("AWS::AccountId"), ":server-certificate/",
            Ref("ELBCertName")])
        with_ssl = copy.deepcopy(no_ssl)
        with_ssl.append(elb.Listener(
            LoadBalancerPort=443,
            InstancePort=80,
            Protocol='HTTPS',
            InstanceProtocol="HTTP",
            SSLCertificateId=cert_id))
        listeners = If("UseSSL", with_ssl, no_ssl)

        return listeners

    def create_load_balancer(self):
        t = self.template
        elb_name = ELB_NAME % self.name
        elb_sg = ELB_SG_NAME % self.name
        t.add_resource(elb.LoadBalancer(
            elb_name,
            HealthCheck=elb.HealthCheck(
                Target='HTTP:80/',
                HealthyThreshold=3,
                UnhealthyThreshold=3,
                Interval=5,
                Timeout=3),
            Listeners=self.setup_listeners(),
            SecurityGroups=[Ref(elb_sg), ],
            Subnets=Ref("PublicSubnets"),
            Condition="CreateELB"))

        # Setup ELB DNS
        t.add_resource(
            RecordSetType(
                '%sDnsRecord' % elb_name,
                # Appends a '.' to the end of the domain
                HostedZoneName=Join("", [Ref("BaseDomain"), "."]),
                Comment='Router ELB DNS',
                Name=Join('.', [Ref("ELBHostName"), Ref("BaseDomain")]),
                Type='CNAME',
                TTL='120',
                ResourceRecords=[
                    GetAtt(elb_name, 'DNSName')],
                Condition="SetupELBDNS"))

    def get_launch_configuration_parameters(self):
        return {
            'ImageId': FindInMap('AmiMap', Ref("AWS::Region"),
                                 Ref('ImageName')),
            'InstanceType': Ref("InstanceType"),
            'KeyName': Ref("SshKeyName"),
            'SecurityGroups': self.get_launch_configuration_security_groups(),
        }

    def get_autoscaling_group_parameters(self, launch_config_name, elb_name):
        return {
            'AvailabilityZones': Ref("AvailabilityZones"),
            'LaunchConfigurationName': Ref(launch_config_name),
            'MinSize': Ref("MinSize"),
            'MaxSize': Ref("MaxSize"),
            'VPCZoneIdentifier': Ref("PrivateSubnets"),
            'LoadBalancerNames': If("CreateELB", [Ref(elb_name), ], []),
            'Tags': [ASTag('Name', self.name, True)],
        }

    def get_launch_configuration_security_groups(self):
        sg_name = CLUSTER_SG_NAME % self.name
        return [Ref("DefaultSG"), Ref(sg_name)]

    def create_autoscaling_group(self):
        name = "%sASG" % self.name
        launch_config = "%sLaunchConfig" % name
        elb_name = ELB_NAME % self.name
        t = self.template
        t.add_resource(autoscaling.LaunchConfiguration(
            launch_config,
            **self.get_launch_configuration_parameters()
        ))
        t.add_resource(autoscaling.AutoScalingGroup(
            name,
            **self.get_autoscaling_group_parameters(launch_config, elb_name)
        ))

    def create_template(self):
        self.create_conditions()
        self.create_security_groups()
        self.create_load_balancer()
        self.create_autoscaling_group()
