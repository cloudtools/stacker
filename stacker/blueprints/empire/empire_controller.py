from troposphere import Ref, Join, Output, GetAtt, Not, Equals, If, FindInMap
from troposphere import ec2, autoscaling
from troposphere.autoscaling import Tag as ASTag
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere import elasticloadbalancing as elb
from troposphere.route53 import RecordSetType

from awacs.helpers.trust import (
    get_default_assumerole_policy, get_ecs_assumerole_policy
)

from .empire_base import EmpireBase

from .policies import (
    service_role_policy,
    empire_policy
)

CLUSTER_SG_NAME = "EmpireControllerSecurityGroup"
ELB_SG_NAME = "EmpireControllerELBSecurityGroup"


class EmpireController(EmpireBase):
    PARAMETERS = {
        "VpcId": {
            "type": "AWS::EC2::VPC::Id",
            "description": "Vpc Id"},
        "DefaultSG": {
            "type": "AWS::EC2::SecurityGroup::Id",
            "description": "Top level security group."},
        "ExternalDomain": {
            "type": "String",
            "description": "Base domain for the stack.",
            "default": ""},
        "InternalZoneId": {
            "type": "AWS::Route53::HostedZone::Id",
            "description": "Zone ID of the internal Empire zone",
            },
        "PrivateSubnets": {
            "type": "List<AWS::EC2::Subnet::Id>",
            "description": "Subnets to deploy private instances in."},
        "PublicSubnets": {
            "type": "List<AWS::EC2::Subnet::Id>",
            "description": "Subnets to deploy public (elb) instances in."},
        "AvailabilityZones": {
            "type": "CommaDelimitedList",
            "description": "Availability Zones to deploy instances in."},
        "InstanceType": {
            "type": "String",
            "description": "Empire AWS Instance Type",
            "default": "m3.medium"},
        "MinHosts": {
            "type": "Number",
            "description": "Minimum # of empire minion instances.",
            "default": "2"},
        "MaxHosts": {
            "type": "Number",
            "description": "Maximum # of empire minion instances.",
            "default": "3"},
        "SshKeyName": {
            "type": "AWS::EC2::KeyPair::KeyName"},
        "TrustedNetwork": {
            "type": "String",
            "description": "CIDR block allowed to connect to empire ELB."},
        "ImageName": {
            "type": "String",
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "NAT"},
        "ControllerELBCertName": {
            "type": "String",
            "description": "The SSL certificate name to use on the ELB. Note: "
                           "If this is set, non-HTTPS access is disabled.",
            "default": ""},
        "PublicEmpireAppELBSG": {
            "type": "AWS::EC2::SecurityGroup::Id",
            "description": "The SG used by the Public App ELBs."},
        "PrivateEmpireAppELBSG": {
            "type": "AWS::EC2::SecurityGroup::Id",
            "description": "The SG used by the Private App ELBs."},
        "EmpireDBSecurityGroup": {
            "type": "AWS::EC2::SecurityGroup::Id",
            "description": "Security group of Empire database."},
        "EmpireDatabaseUser": {
            "type": "String",
            "description": "User for empire database."},
        "EmpireDatabasePassword": {
            "type": "String",
            "no_echo": True,
            "description": "Password for empire database."},
        "EmpireDatabaseHost": {
            "type": "String",
            "description": "Hostname for empire database."},
        "EmpireMinionCluster": {
            "type": "String",
            "description": "ECS Cluster Name for Empire Minion Hosts."},
        "EmpireGithubClientId": {
            "type": "String",
            "description": "Github Client Id to enable Github Authentication "
                           "in Empire."},
        "EmpireGithubClientSecret": {
            "type": "String",
            "no_echo": True,
            "description": "Github Client Secret to enable Github "
                           "Authentication in Empire."},
        "EmpireGithubOrganization": {
            "type": "String",
            "description": "Github Organization to enable Github "
                           "Authentication in Empire."},
        "EmpireTokenSecret": {
            "type": "String",
            "no_echo": True,
            "description": "Secret used to sign Empire access tokens."},
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
            "default": ""},
    }

    def create_conditions(self):
        self.template.add_condition(
            "UseSSL",
            Not(Equals(Ref("ControllerELBCertName"), "")))
        self.template.add_condition(
            "UseDNS",
            Not(Equals(Ref("ExternalDomain"), "")))
        self.template.add_condition(
            "EnableStreamingLogs",
            Equals(Ref("DisableStreamingLogs"), ""))

    def create_security_groups(self):
        t = self.template

        t.add_resource(
            ec2.SecurityGroup(
                CLUSTER_SG_NAME, GroupDescription=CLUSTER_SG_NAME,
                VpcId=Ref("VpcId")))
        t.add_output(
            Output('EmpireControllerSG', Value=Ref(CLUSTER_SG_NAME)))

        # Allow access to the DB
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerDBAccess",
                IpProtocol='tcp', FromPort=5432, ToPort=5432,
                SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                GroupId=Ref('EmpireDBSecurityGroup')))

        # Now setup all Empire ELB SG stuff
        t.add_resource(
            ec2.SecurityGroup(
                ELB_SG_NAME, GroupDescription=ELB_SG_NAME,
                VpcId=Ref("VpcId")))
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerELBPort80FromTrusted",
                IpProtocol='tcp', FromPort='80', ToPort='80',
                CidrIp=Ref("TrustedNetwork"), GroupId=Ref(ELB_SG_NAME)))
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerELBPort443FromTrusted",
                IpProtocol='tcp', FromPort='443', ToPort='443',
                CidrIp=Ref("TrustedNetwork"), GroupId=Ref(ELB_SG_NAME)))

        t.add_resource(
            ec2.SecurityGroupIngress(
                "ELBPort80ToControllerPort8080",
                IpProtocol='tcp', FromPort='8080', ToPort='8080',
                SourceSecurityGroupId=Ref(ELB_SG_NAME),
                GroupId=Ref(CLUSTER_SG_NAME)))

    def setup_listeners(self):
        no_ssl = [elb.Listener(
            LoadBalancerPort=80,
            Protocol='TCP',
            InstancePort=8080,
            InstanceProtocol='TCP'
        )]

        cert_id = Join("", [
            "arn:aws:iam::", Ref("AWS::AccountId"), ":server-certificate/",
            Ref("ControllerELBCertName")])
        with_ssl = []
        with_ssl.append(elb.Listener(
            LoadBalancerPort=443,
            InstancePort=8080,
            Protocol='SSL',
            InstanceProtocol="TCP",
            SSLCertificateId=cert_id))
        listeners = If("UseSSL", with_ssl, no_ssl)

        return listeners

    def create_load_balancer(self):
        t = self.template
        t.add_resource(
            elb.LoadBalancer(
                'EmpireControllerLoadBalancer',
                HealthCheck=elb.HealthCheck(
                    Target='HTTP:8080/health',
                    HealthyThreshold=3,
                    UnhealthyThreshold=3,
                    Interval=5,
                    Timeout=3),
                Listeners=self.setup_listeners(),
                SecurityGroups=[Ref(ELB_SG_NAME), ],
                Subnets=Ref("PublicSubnets")))

        # Setup ELB DNS
        t.add_resource(
            RecordSetType(
                'EmpireControllerElbDnsRecord',
                Condition="UseDNS",
                HostedZoneName=Join("", [Ref("ExternalDomain"), "."]),
                Comment='Router ELB DNS',
                Name=Join('.', ["empire", Ref("ExternalDomain")]),
                Type='CNAME',
                TTL='120',
                ResourceRecords=[
                    GetAtt("EmpireControllerLoadBalancer", 'DNSName')]))

    def build_block_device(self):
        volume = autoscaling.EBSBlockDevice(VolumeSize='50')
        return [autoscaling.BlockDeviceMapping(
            DeviceName='/dev/sdh', Ebs=volume)]

    def create_iam_profile(self):
        t = self.template
        # Create EC2 Container Service Role
        t.add_resource(
            Role(
                "ecsServiceRole",
                AssumeRolePolicyDocument=get_ecs_assumerole_policy(),
                Path="/",
                Policies=[
                    Policy(PolicyName="ecsServiceRolePolicy",
                           PolicyDocument=service_role_policy())
                ]))

        # Role for Empire Controllers
        t.add_resource(
            Role(
                "EmpireControllerRole",
                AssumeRolePolicyDocument=get_default_assumerole_policy(),
                Path="/",
                Policies=[
                    Policy(PolicyName="EmpireControllerPolicy",
                           PolicyDocument=empire_policy())]))
        t.add_resource(
            InstanceProfile(
                "EmpireControllerProfile",
                Path="/",
                Roles=[Ref("EmpireControllerRole")]))

    def generate_seed_contents(self):
        seed = [
            "EMPIRE_HOSTGROUP=controller\n",
            "EMPIRE_ECS_SERVICE_ROLE=", Ref("ecsServiceRole"), "\n",
            "EMPIRE_ELB_SG_PRIVATE=", Ref("PrivateEmpireAppELBSG"), "\n",
            "EMPIRE_ELB_SG_PUBLIC=", Ref("PublicEmpireAppELBSG"), "\n",
            "EMPIRE_EC2_SUBNETS_PRIVATE=",
            Join(",", Ref("PrivateSubnets")), "\n",
            "EMPIRE_EC2_SUBNETS_PUBLIC=",
            Join(",", Ref("PublicSubnets")), "\n",
            "EMPIRE_DATABASE_USER=", Ref("EmpireDatabaseUser"), "\n",
            "EMPIRE_DATABASE_PASSWORD=", Ref("EmpireDatabasePassword"), "\n",
            "EMPIRE_DATABASE_HOST=", Ref("EmpireDatabaseHost"), "\n",
            "EMPIRE_ROUTE53_INTERNAL_ZONE_ID=", Ref("InternalZoneId"), "\n",
            "ECS_CLUSTER=", Ref("EmpireMinionCluster"), "\n",
            "EMPIRE_GITHUB_CLIENT_ID=", Ref("EmpireGithubClientId"), "\n",
            "EMPIRE_GITHUB_CLIENT_SECRET=", Ref("EmpireGithubClientSecret"),
            "\n",
            "EMPIRE_GITHUB_ORGANIZATION=", Ref("EmpireGithubOrganization"),
            "\n",
            "EMPIRE_TOKEN_SECRET=", Ref("EmpireTokenSecret"), "\n",
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
                'EmpireControllerLaunchConfig',
                IamInstanceProfile=GetAtt("EmpireControllerProfile",
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
                'EmpireControllerAutoscalingGroup',
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref("EmpireControllerLaunchConfig"),
                MinSize=Ref("MinHosts"),
                MaxSize=Ref("MaxHosts"),
                VPCZoneIdentifier=Ref("PrivateSubnets"),
                LoadBalancerNames=[Ref("EmpireControllerLoadBalancer"), ],
                Tags=[ASTag('Name', 'empire_controller', True)]))
