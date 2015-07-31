from troposphere import Ref, ec2, Output, GetAtt
from troposphere.elasticache import (
    ReplicationGroup,
    SubnetGroup,
)

from .base import Blueprint


class RedisCluster(Blueprint):
    PARAMETERS = {
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
        'CacheClusterId': {
            'type': 'String',
            'description': 'The node group identifier',
        },
        'PrivateSubnets': {
            'type': 'List<AWS::EC2::Subnet::Id>',
            'description': 'Subnets to deploy private instances in.',
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

    def __init__(self, *args, **kwargs):
        super(RedisCluster, self).__init__(*args, **kwargs)
        self.subnet_group_name = '%sSubnetGroup' % (self.name,)
        self.security_group_name = '%sElastiCacheSG' % (self.name,)
        self.replication_group_name = '%sRedisReplicationGroup' % (self.name,)

    def create_subnet_group(self):
        t = self.template
        subnet_group = SubnetGroup(
            self.subnet_group_name,
            Description='%s VPC subnet group.' % (self.name,),
            SubnetIds=Ref('PrivateSubnets'),
        )
        t.add_resource(subnet_group)

    def create_security_group(self):
        t = self.template
        security_group = ec2.SecurityGroup(
            self.security_group_name,
            GroupDescription='%s ElastiCache security group' % (self.security_group_name,),
            VpcId=Ref('VpcId'),
        )
        resource = t.add_resource(security_group)
        t.add_output(Output('SecurityGroup', Value=Ref(resource)))

    def create_replication_group(self):
        t = self.template
        replication_group = ReplicationGroup(
            self.replication_group_name,
            AutomaticFailoverEnabled=Ref('AutomaticFailoverEnabled'),
            CacheNodeType=Ref('CacheNodeType'),
            CacheSubnetGroupName=Ref(self.subnet_group_name),
            Engine='redis',
            EngineVersion='2.8.19',
            NumCacheClusters=Ref('NumCacheClusters'),
            ReplicationGroupDescription='%s replication group' % (self.replication_group_name,),
            PreferredMaintenanceWindow=Ref('PreferredMaintenanceWindow'),
            SecurityGroupIds=[GetAtt(self.security_group_name, 'GroupId')],
        )
        resource = t.add_resource(replication_group)
        t.add_output(Output('ReplicationGroup', Value=Ref(resource)))

        primary_address = GetAtt(self.replication_group_name, 'PrimaryEndPoint.Address')
        read_addresses = GetAtt(self.replication_group_name, 'ReadEndPoint.Addresses')
        t.add_output(Output('PrimaryAddress', Value=primary_address))
        t.add_output(Output('ReadAddresses', Value=read_addresses))

    def create_template(self):
        self.create_subnet_group()
        self.create_security_group()
        self.create_replication_group()
