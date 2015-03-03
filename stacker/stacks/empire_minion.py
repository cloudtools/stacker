# from base64 import b64encode

# import yaml
from troposphere import Ref, FindInMap, Parameter, Base64, Join
from troposphere import ec2, autoscaling
from troposphere.autoscaling import Tag as ASTag

from ..stack import StackTemplateBase
from ..keys import SSH_KEYS

CLUSTER_SG_NAME = "EmpireMinionSecurityGroup"


class EmpireMinion(StackTemplateBase):
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
                         'description': 'Empire AWS Instance Type',
                         'default': 'c4.2xlarge'},
        'MinSize': {'type': 'Number',
                    'description': 'Minimum # of coreos instances.',
                    'default': '3'},
        'MaxSize': {'type': 'Number',
                    'description': 'Maximum # of coreos instances.',
                    'default': '20'},
        'SshKeyName': {'type': 'AWS::EC2::KeyPair::KeyName'},
        'DiscoveryURL': {'type': 'String'},
        'EmpireControllerSG': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Security group for the empire controller '
                           'cluster.'},
    }

    def create_parameters(self):
        t = self.template
        for param, attrs in self.PARAMETERS.items():
            p = Parameter(param,
                          Type=attrs.get('type'),
                          Description=attrs.get('description', ''))
            if 'default' in attrs:
                p.Default = attrs['default']
            t.add_parameter(p)

    def create_security_groups(self):
        t = self.template
        t.add_resource(
            ec2.SecurityGroup(CLUSTER_SG_NAME,
                              GroupDescription='EmpireMinionSecurityGroup',
                              VpcId=Ref("VpcId")))
        # Give Minions access to Etcd (4001)
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireMinionEtcdAccess",
                IpProtocol='tcp', FromPort=4001, ToPort=4001,
                SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                GroupId=Ref('EmpireControllerSG')))
        # Give Controller's ssh access to minions
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerSSHAccess",
                IpProtocol='tcp', FromPort=22, ToPort=22,
                SourceSecurityGroupId=Ref('EmpireControllerSG'),
                GroupId=Ref(CLUSTER_SG_NAME)))
        # Allow all ports within cluster
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireMinionAllTCPAccess",
                IpProtocol='-1', FromPort='-1', ToPort='-1',
                SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                GroupId=Ref(CLUSTER_SG_NAME)))
        # TODO: Allow Router to connect to any of the following ports:
        # 49153-65535

    def generate_user_data(self):
        key_string = '\n'.join(["  - %s" % key for key in SSH_KEYS]) + '\n'
        user_data = [
            "#cloud-config\n\n",
            "coreos:\n",
            "  fleet:\n",
            "    metadata: \"role=empire_minion\"\n",

            "  units:\n",
            "    - command: start\n",
            "      name: etcd_peers.service\n",
            "      content: |\n",
            "        [Unit]\n",
            "        Description=etcd_peers service\n",
            "        Before=fleet.service\n",
            "        [Service]\n",
            "        TimeoutStartSec=0\n",
            "        Type=oneshot\n",
            "        User=core\n",
            "        ExecStartPre=-/bin/docker kill etcd_peers\n",
            "        ExecStartPre=-/bin/docker rm etcd_peers\n",
            "        ExecStartPre=/bin/sudo /bin/mkdir -p "
            "/etc/sysconfig\n",
            "        ExecStartPre=/bin/docker pull ",
            "quay.io/remind/etcd_peers:latest\n",
            "        ExecStart=/bin/docker run ",
            "--name etcd_peers -v /etc/sysconfig:/mnt ",
            "quay.io/remind/etcd_peers /home/app/app ",
            "-output=/mnt/fleet.cf ", Ref('DiscoveryURL'), "\n"

            "    - command: start\n",
            "      name: fleet.service\n",

            "ssh_authorized_keys:\n",
            key_string,

            "write_files:\n",
            "    - path: /home/core/.dockercfg\n",
            "      permissions: 0600\n",
            "      owner: core\n",
            "      content: |\n",
            "        {\"quay.io\":{\"auth\":\"bWlrZTA6dTg0VSFTcVNlZlIjOEghZA=",
            "=\",\"email\":\"mike@remind101.com\"}}\n",
            "    - path: /etc/systemd/system/fleet.socket.d/30-ListenStream",
            ".conf\n",
            "      permissions: 0644\n",
            "      owner: root\n",
            "      content: |\n",
            "        [Socket]\n",
            "        ListenStream=$private_ipv4:9000\n",
            "    - path: /etc/systemd/system/fleet.service.d/"
            "10-EtcdPeers.conf\n",
            "      owner: root\n",
            "      permissions: 0644\n",
            "      content: |\n",
            "        [Service]\n",
            "        EnvironmentFile=/etc/sysconfig/fleet.cf\n"
        ]
        ud = Base64(Join("", user_data))
        return ud

    def create_autoscaling_group(self):
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                'EmpireMinionLaunchConfig',
                ImageId=FindInMap('AmiMap', Ref("AWS::Region"), 'coreos'),
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

    def create_template(self):
        self.create_parameters()
        self.create_security_groups()
        self.create_autoscaling_group()
