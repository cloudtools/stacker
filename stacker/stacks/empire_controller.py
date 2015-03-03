# from base64 import b64encode

# import yaml
from troposphere import Ref, FindInMap, Parameter, Base64, Join, Output
from troposphere import ec2, autoscaling
from troposphere.autoscaling import Tag as ASTag

from ..stack import StackTemplateBase
from ..keys import SSH_KEYS

CLUSTER_SG_NAME = "EmpireControllerSecurityGroup"


class EmpireController(StackTemplateBase):
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
                         'default': 'c4.xlarge'},
        'MinSize': {'type': 'Number',
                    'description': 'Minimum # of coreos instances.',
                    'default': '5'},
        'MaxSize': {'type': 'Number',
                    'description': 'Maximum # of coreos instances.',
                    'default': '5'},
        'SshKeyName': {'type': 'AWS::EC2::KeyPair::KeyName'},
        'DiscoveryURL': {'type': 'String'},
        'DBSecurityGroup': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Database security group.'},
        'DBURL': {
            'type': 'String',
            'description': 'Database connection url.'}
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
        ports = [4001, 7001, 22]

        t.add_resource(
            ec2.SecurityGroup(CLUSTER_SG_NAME,
                              GroupDescription='EmpireControllerSecurityGroup',
                              VpcId=Ref("VpcId")))
        t.add_output(
            Output('EmpireControllerSG', Value=Ref(CLUSTER_SG_NAME)))

        for port in ports:
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "EmpireControllerPeerPort%d" % port,
                    IpProtocol='tcp', FromPort=port, ToPort=port,
                    SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                    GroupId=Ref(CLUSTER_SG_NAME)))

        # Add rule for access to DB
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerDBAccess",
                IpProtocol='tcp', FromPort=5432, ToPort=5432,
                SourceSecurityGroupId=Ref(CLUSTER_SG_NAME),
                GroupId=Ref('DBSecurityGroup')))

    def generate_user_data(self):
        key_string = '\n'.join(["  - %s" % key for key in SSH_KEYS]) + '\n'
        user_data = [
            "#cloud-config\n\n",
            "coreos:\n",
            "  etcd:\n"
            "    discovery: ", Ref("DiscoveryURL"), "\n",
            "    addr: $private_ipv4:4001\n",
            "    peer-addr: $private_ipv4:7001\n",
            "  fleet:\n",
            "    metadata: \"role=empire_controller\"\n",
            "  units:\n",
            "    - command: start\n",
            "      name: etcd.service\n",
            "    - command: start\n",
            "      name: fleet.service\n",

            "    - name: empire_migrate.service\n",
            "      command: start\n",
            "      content: |\n",
            "        [Unit]\n",
            "        Description=Empire Database Migration\n",
            "        Before=empire.service\n\n",
            "        [Service]\n",
            "        TimeoutStartSec=0\n",
            "        Type=oneshot\n",
            "        User=core\n",
            "        ExecStartPre=-/bin/docker kill empire_migrate\n",
            "        ExecStartPre=-/bin/docker rm empire_migrate\n",
            "        ExecStartPre=/bin/docker pull ",
            "quay.io/remind/empire:latest\n",
            "        ExecStart=/bin/docker run ",
            "--name empire_migrate ",
            "quay.io/remind/empire migrate ",
            "--db '", Ref('DBURL'), "?sslmode=disable'\n",

            "    - name: empire.service\n",
            "      command: start\n",
            "      content: |\n",
            "        [Unit]\n",
            "        Description=The Empire PaaS Service\n\n",
            "        [Service]\n",
            "        TimeoutStartSec=0\n",
            "        User=core\n",
            "        KillMode=none\n",
            "        Restart=on-failure\n",
            "        ExecStartPre=-/bin/docker kill empire\n",
            "        ExecStartPre=-/bin/docker rm empire\n",
            "        ExecStartPre=/bin/docker pull ",
            "quay.io/remind/empire:latest\n",
            "        ExecStart=/bin/docker run -p 8080:8080 -v ",
            "/var/run/docker.sock:/var/run/docker.sock --name empire ",
            "quay.io/remind/empire server --docker.registry quay.io ",
            "--fleet.api 'http://$private_ipv4:9000' ",
            "--db '", Ref('DBURL'), "?sslmode=disable'\n",

            "ssh_authorized_keys:\n",
            key_string,

            "write_files:\n",
            "    - path: /etc/sysconfig/empire_db.cf\n",
            "      permissions: 0644\n",
            "      owner: root\n",
            "      content: DATABASE_URL=\"", Ref('DBURL'), "\"\n",
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
        ]
        ud = Base64(Join("", user_data))
        return ud

    def create_autoscaling_group(self):
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                'EmpireControllerLaunchConfig',
                ImageId=FindInMap('AmiMap', Ref("AWS::Region"), 'coreos'),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
                UserData=self.generate_user_data(),
                SecurityGroups=[Ref("DefaultSG"), Ref(CLUSTER_SG_NAME)]))
        t.add_resource(
            autoscaling.AutoScalingGroup(
                'EmpireControllerAutoscalingGroup',
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref("EmpireControllerLaunchConfig"),
                MinSize=Ref("MinSize"),
                MaxSize=Ref("MaxSize"),
                VPCZoneIdentifier=Ref("PrivateSubnets"),
                Tags=[ASTag('Name', 'empire_controller', True)]))

    def create_template(self):
        self.create_parameters()
        self.create_security_groups()
        self.create_autoscaling_group()
