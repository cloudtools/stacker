from troposphere import Ref, ec2, Output, GetAtt
from troposphere.elasticache import ReplicationGroup, SubnetGroup

from .base import Blueprint

SUBNET_GROUP = 'RedisSubnetGroup'
SECURITY_GROUP = 'RedisSecurityGroup'
REPLICATION_GROUP = 'RedisReplicationGroup'


class RedisCluster(Blueprint):
    PARAMETERS = {
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
        'CacheClusterId': {
            'type': 'String',
            'description': 'The node group identifier',
        },
        'Subnets': {
            'type': 'List<AWS::EC2::Subnet::Id>',
            'description': 'Subnets to deploy instances in.',
        },
        'CacheNodeType': {
            'type': 'String',
            'description': 'ElastiCache Instance Type',
            'default': 'cache.m3.large',
        },
        'PreferredMaintenanceWindow': {
            'type': 'String',
            'description': (
                'A (minimum 60 minute) window in '
                'ddd:hh24:mi-ddd:hh24:mi format in UTC for '
                'maintence. Default: Sunday 2am-3am'
            ),
            'default': 'sun:02:00-sun:03:00',
        },
        'AutomaticFailoverEnabled': {
            'type': 'String',
            'description': (
                'Specifies whether a read-only replica will be automatically '
                'promoted to read/write primary if the existing primary fails. '
                'If true, Multi-AZ is enabled for this replication group. If '
                'false, Multi-AZ is disabled for this replication group.'
            ),
            'default': 'true',
            'allowed_values': ['true', 'false'],
        },
        'NumCacheClusters': {
            'type': 'Number',
            'description': (
                'The number of cache clusters this replication group will '
                'initially have. If Multi-AZ is enabled, the value of this '
                'parameter must be at least 2.'
            ),
            'default': '2',
        },
    }

    def create_subnet_group(self):
        t = self.template
        subnet_group = SubnetGroup(
            SUBNET_GROUP,
            Description='%s VPC subnet group.' % (self.name,),
            SubnetIds=Ref('Subnets'),
        )
        t.add_resource(subnet_group)

    def create_security_group(self):
        t = self.template
        security_group = ec2.SecurityGroup(
            SECURITY_GROUP,
            GroupDescription='%s ElastiCache security group' % (SECURITY_GROUP,),
            VpcId=Ref('VpcId'),
        )
        resource = t.add_resource(security_group)
        t.add_output(Output('SecurityGroup', Value=Ref(resource)))

    def create_replication_group(self):
        t = self.template
        replication_group = ReplicationGroup(
            REPLICATION_GROUP,
            AutomaticFailoverEnabled=Ref('AutomaticFailoverEnabled'),
            CacheNodeType=Ref('CacheNodeType'),
            CacheSubnetGroupName=Ref(SUBNET_GROUP),
            Engine='redis',
            EngineVersion='2.8.19',
            NumCacheClusters=Ref('NumCacheClusters'),
            ReplicationGroupDescription='%s replication group' % (REPLICATION_GROUP,),
            PreferredMaintenanceWindow=Ref('PreferredMaintenanceWindow'),
            SecurityGroupIds=[GetAtt(SECURITY_GROUP, 'GroupId')],
        )
        resource = t.add_resource(replication_group)
        t.add_output(Output('ReplicationGroup', Value=Ref(resource)))

        primary_address = GetAtt(REPLICATION_GROUP, 'PrimaryEndPoint.Address')
        read_addresses = GetAtt(REPLICATION_GROUP, 'ReadEndPoint.Addresses')
        t.add_output(Output('PrimaryAddress', Value=primary_address))
        t.add_output(Output('ReadAddresses', Value=read_addresses))

    def create_template(self):
        self.create_subnet_group()
        self.create_security_group()
        self.create_replication_group()
