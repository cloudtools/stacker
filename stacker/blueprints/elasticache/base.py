from troposphere import (
    Ref, ec2, Output, GetAtt, Not, Equals, Condition, And, Join, If
)

from troposphere.elasticache import (
    ReplicationGroup, ParameterGroup, SubnetGroup
)

from troposphere.route53 import RecordSetType

from ..base import Blueprint

# Resource name constants
SUBNET_GROUP = "SubnetGroup"
SECURITY_GROUP = "SecurityGroup"
REPLICATION_GROUP = "ReplicationGroup"
DNS_RECORD = "ReplicationGroupDnsRecord"
PARAMETER_GROUP = "ParameterGroup"


class BaseReplicationGroup(Blueprint):
    """Base Blueprint for all Elasticache ReplicationGroup blueprints.

    ReplicationGroups are only currently supported by the redis engine.
    """

    ALLOWED_ENGINES = ["redis"]

    LOCAL_PARAMETERS = {
        "ClusterParameters": {
            "type": dict,
            "default": {},
        },
    }

    def engine(self):
        return None

    def get_engine_versions(self):
        """Used by engine specific subclasses - returns valid engine versions.

        Should only be overridden if the class variable ENGINE is defined on
        the class.

        Return:
            list: A list of valid engine versions for the given engine.
        """
        return []

    def get_parameter_group_family(self):
        """Used by engine specific subclasses to return parameter group family.

        Should only be overridden if the class variable ENGINE is defined on
        the class.

        Return:
            list: A list of valid parameter group families for the given
                  engine.
        """
        return []

    def _get_parameters(self):
        parameters = {
            "VpcId": {
                "type": "AWS::EC2::VPC::Id",
                "description": "Vpc Id to place the Cluster in"
            },
            "Subnets": {
                "type": "List<AWS::EC2::Subnet::Id>",
                "description": "Subnets to deploy the Cluster nodes in."
            },
            "ParameterGroupFamily": {
                "type": "String",
                "description": "The parametergroup family to use, dependent "
                               "on the engine.",
                "allowed_values": self.get_parameter_group_family()
            },
            "AutomaticFailoverEnabled": {
                "type": "String",
                "description": "Set to false to disallow automatic failover "
                               "in the case of a node failure.",
                "default": "true",
                "allowed_values": ["true", "false"]
            },
            "AutoMinorVersionUpgrade": {
                "type": "String",
                "description": "Set to 'true' to allow minor version upgrades "
                               "during maintenance windows.",
                "default": "false",
                "allowed_values": ["true", "false"]
            },
            "CacheNodeType": {
                "type": "String",
                "description": "AWS ElastiCache Cache Node Type",
                "default": "cache.t2.medium"
            },
            "EngineVersion": {
                "type": "String",
                "description": "Engine version for the Cache Cluster.",
            },
            "NotificationTopicArn": {
                "type": "String",
                "description": "ARN of the SNS Topic to publish events to.",
                "default": "",
            },
            "NumCacheClusters": {
                "type": "Number",
                "description": "The # of nodes to bring up in the cluster.",
                "default": "2",
                "min_value": "1",
            },
            "Port": {
                "type": "Number",
                "description": "The port to run the cluster on.",
                "default": "0",
            },
            "PreferredCacheClusterAZs": {
                "type": "CommaDelimitedList",
                "description": "Must match the # of nodes in "
                               "NumCacheClusters.",
                "default": "",
            },
            "PreferredMaintenanceWindow": {
                "type": "String",
                "description": "A (minimum 60 minute) window in "
                               "DDD:HH:MM-DDD:HH:MM format in UTC for "
                               "backups. Default: Sunday 3am-4am PST",
                "default": "Sun:11:00-Sun:12:00"
            },
            "SnapshotArns": {
                "type": "CommaDelimitedList",
                "description": "A list of s3 ARNS where redis snapshots are "
                               "stored that will be used to create the "
                               "cluster.",
                "default": "",
            },
            "SnapshotRetentionLimit": {
                "type": "Number",
                "description": "The number of daily snapshots to retain. Only "
                               "valid for clusters with the redis Engine.",
                "default": "0",
            },
            "SnapshotWindow": {
                "type": "String",
                "description": "For Redis cache clusters, daily time range "
                               "(in UTC) during which ElastiCache will begin "
                               "taking a daily snapshot of your node group. "
                               "For example, you can specify 05:00-09:00.",
                "default": ""
            },
            "InternalZoneId": {
                "type": "String",
                "default": "",
                "description": "Internal zone Id, if you have one."
            },
            "InternalZoneName": {
                "type": "String",
                "default": "",
                "description": "Internal zone name, if you have one."
            },
            "InternalHostname": {
                "type": "String",
                "default": "",
                "description": "Internal domain name, if you have one."
            },
        }

        engine_versions = self.get_engine_versions()
        if engine_versions:
            parameters['EngineVersion']['allowed_values'] = engine_versions

        if not self.engine():
            parameters['Engine'] = {
                "type": "String",
                "description": "Database engine for the RDS Instance.",
                "allowed_values": self.ALLOWED_ENGINES
            }
        else:
            if self.engine() not in self.ALLOWED_ENGINES:
                raise ValueError("ENGINE must be one of: %s" %
                                 ", ".join(self.ALLOWED_ENGINES))

        return parameters

    def create_conditions(self):
        t = self.template

        t.add_condition(
            "DefinedNotificationArn",
            Not(Equals(Ref("NotificationTopicArn"), "")))
        t.add_condition(
            "DefinedPort",
            Not(Equals(Ref("Port"), "0")))
        t.add_condition(
            "DefinedAvailabilityZones",
            Not(Equals(Join(",", Ref("PreferredCacheClusterAZs")), "")))
        t.add_condition(
            "DefinedSnapshotArns",
            Not(Equals(Join(",", Ref("SnapshotArns")), "")))
        t.add_condition(
            "DefinedSnapshotWindow",
            Not(Equals(Ref("SnapshotWindow"), "")))

        # DNS Conditions
        t.add_condition(
            "HasInternalZone",
            Not(Equals(Ref("InternalZoneId"), "")))
        t.add_condition(
            "HasInternalZoneName",
            Not(Equals(Ref("InternalZoneName"), "")))
        t.add_condition(
            "HasInternalHostname",
            Not(Equals(Ref("InternalHostname"), "")))
        t.add_condition(
            "CreateInternalHostname",
            And(Condition("HasInternalZone"),
                Condition("HasInternalZoneName"),
                Condition("HasInternalHostname")))

    def create_parameter_group(self):
        t = self.template
        params = self.local_parameters["ClusterParameters"]
        t.add_resource(
            ParameterGroup(
                PARAMETER_GROUP,
                Description=self.name,
                CacheParameterGroupFamily=Ref("ParameterGroupFamily"),
                Properties=params,
            )
        )

    def create_subnet_group(self):
        t = self.template
        t.add_resource(
            SubnetGroup(
                SUBNET_GROUP,
                Description="%s subnet group." % self.name,
                SubnetIds=Ref("Subnets")))

    def create_security_group(self):
        t = self.template
        sg = t.add_resource(
            ec2.SecurityGroup(
                SECURITY_GROUP,
                GroupDescription="%s security group" % self.name,
                VpcId=Ref("VpcId")))
        t.add_output(Output("SecurityGroup", Value=Ref(sg)))

    def create_replication_group(self):
        t = self.template
        availability_zones = If("DefinedAvailabilityZones",
                                Ref("PreferredCacheClusterAZs"),
                                Ref("AWS::NoValue"))
        t.add_resource(
            ReplicationGroup(
                REPLICATION_GROUP,
                AutomaticFailoverEnabled=Ref("AutomaticFailoverEnabled"),
                AutoMinorVersionUpgrade=Ref("AutoMinorVersionUpgrade"),
                CacheNodeType=Ref("CacheNodeType"),
                CacheParameterGroupName=Ref(PARAMETER_GROUP),
                CacheSubnetGroupName=Ref(SUBNET_GROUP),
                Engine=self.engine() or Ref("Engine"),
                EngineVersion=Ref("EngineVersion"),
                NotificationTopicArn=If("DefinedNotificationArn",
                                        Ref("NotificationTopicArn"),
                                        Ref("AWS::NoValue")),
                NumCacheClusters=Ref("NumCacheClusters"),
                Port=If("DefinedPort",
                        Ref("Port"),
                        Ref("AWS::NoValue")),
                PreferredCacheClusterAZs=availability_zones,
                PreferredMaintenanceWindow=Ref("PreferredMaintenanceWindow"),
                ReplicationGroupDescription=self.name,
                SecurityGroupIds=[Ref(SECURITY_GROUP), ],
                SnapshotArns=If("DefinedSnapshotArns",
                                Ref("SnapshotArns"),
                                Ref("AWS::NoValue")),
                SnapshotRetentionLimit=Ref("SnapshotRetentionLimit"),
                SnapshotWindow=If("DefinedSnapshotWindow",
                                  Ref("SnapshotWindow"),
                                  Ref("AWS::NoValue")),
            )
        )

    def get_primary_address(self):
        return GetAtt(REPLICATION_GROUP, "PrimaryEndPoint.Address")

    def get_secondary_addresses(self):
        return GetAtt(REPLICATION_GROUP, "ReadEndPoint.Addresses.List")

    def create_dns_records(self):
        t = self.template
        primary_endpoint = self.get_primary_address()

        t.add_resource(
            RecordSetType(
                DNS_RECORD,
                HostedZoneId=Ref("InternalZoneId"),
                Comment="ReplicationGroup CNAME Record",
                Name=Join(".", [Ref("InternalHostname"),
                          Ref("InternalZoneName")]),
                Type="CNAME",
                TTL="120",
                ResourceRecords=[primary_endpoint],
                Condition="CreateInternalHostname"))

    def create_cluster_outputs(self):
        t = self.template
        t.add_output(Output("PrimaryAddress",
                            Value=self.get_primary_address()))
        t.add_output(Output("ReadAddresses",
                            Value=Join(",", self.get_secondary_addresses())))

        t.add_output(Output("ClusterPort",
                            Value=GetAtt(REPLICATION_GROUP,
                                         "PrimaryEndPoint.Port")))
        t.add_output(Output("ClusterId", Value=Ref(REPLICATION_GROUP)))
        t.add_output(
            Output(
                "PrimaryCname",
                Condition="CreateInternalHostname",
                Value=Ref(DNS_RECORD)))

    def create_template(self):
        self.create_conditions()
        self.create_parameter_group()
        self.create_subnet_group()
        self.create_security_group()
        self.create_replication_group()
        self.create_dns_records()
        self.create_cluster_outputs()
