import warnings

warnings.warn("The included blueprints are deprecated. You should install "
              "the `stacker_blueprints` module instead.",
              DeprecationWarning)

from troposphere import (
    Ref, ec2, Output, GetAtt, Not, Equals, Condition, And, Join
)
from troposphere.rds import DBInstance, DBSubnetGroup
from troposphere.route53 import RecordSetType


from .base import Blueprint

RDS_INSTANCE_NAME = "PostgresRDS%s"
RDS_SUBNET_GROUP = "%sSubnetGroup"
RDS_SG_NAME = "RdsSG%s"


class PostgresRDS(Blueprint):
    PARAMETERS = {
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
        'PrivateSubnets': {'type': 'List<AWS::EC2::Subnet::Id>',
                           'description': 'Subnets to deploy private '
                                          'instances in.'},
        'InstanceType': {'type': 'String',
                         'description': 'AWS RDS Instance Type',
                         'default': 'db.m3.large'},
        'AllocatedStorage': {'type': 'Number',
                             'description': 'Space, in GB, to allocate to RDS '
                                            'instance.',
                             'default': '10'},
        'MasterUser': {'type': 'String',
                       'description': 'Name of the master user in the db.',
                       'default': 'dbuser'},
        'MasterUserPassword': {'type': 'String',
                               'description': 'Master user password.'},
        'PreferredBackupWindow': {
            'type': 'String',
            'description': 'A (minimum 30 minute) window in HH:MM-HH:MM '
                           'format in UTC for backups. Default: 3am-4am',
            'default': '11:00-12:00'},
        'DBName': {
            'type': 'String',
            'description': 'Initial db to create in database.'},
        "InternalZoneId": {
            "type": "String",
            "default": "",
            "description": "Internal zone Id, if you have one."},
        "InternalZoneName": {
            "type": "String",
            "default": "",
            "description": "Internal zone name, if you have one."},
        "InternalHostname": {
            "type": "String",
            "default": "",
            "description": "Internal domain name, if you have one."},
    }

    def create_conditions(self):
        self.template.add_condition(
            "HasInternalZone",
            Not(Equals(Ref("InternalZoneId"), "")))
        self.template.add_condition(
            "HasInternalZoneName",
            Not(Equals(Ref("InternalZoneName"), "")))
        self.template.add_condition(
            "HasInternalHostname",
            Not(Equals(Ref("InternalHostname"), "")))
        self.template.add_condition(
            "CreateInternalHostname",
            And(Condition("HasInternalZone"),
                Condition("HasInternalZoneName"),
                Condition("HasInternalHostname")))

    def create_subnet_group(self):
        t = self.template
        t.add_resource(
            DBSubnetGroup(
                RDS_SUBNET_GROUP % self.name,
                DBSubnetGroupDescription="%s VPC subnet group." % self.name,
                SubnetIds=Ref('PrivateSubnets')))

    def create_security_group(self):
        t = self.template
        sg_name = RDS_SG_NAME % self.name
        sg = t.add_resource(
            ec2.SecurityGroup(
                sg_name,
                GroupDescription='%s RDS security group' % sg_name,
                VpcId=Ref("VpcId")))
        t.add_output(Output("SecurityGroup", Value=Ref(sg)))

    def create_rds(self):
        t = self.template
        db_name = RDS_INSTANCE_NAME % self.name
        t.add_resource(
            DBInstance(
                db_name,
                AllocatedStorage=Ref('AllocatedStorage'),
                AllowMajorVersionUpgrade=False,
                AutoMinorVersionUpgrade=True,
                BackupRetentionPeriod=30,
                DBName=Ref('DBName'),
                DBInstanceClass=Ref('InstanceType'),
                DBSubnetGroupName=Ref(RDS_SUBNET_GROUP % self.name),
                Engine='postgres',
                EngineVersion='9.3.5',
                MasterUsername=Ref('MasterUser'),
                MasterUserPassword=Ref('MasterUserPassword'),
                MultiAZ=True,
                PreferredBackupWindow=Ref('PreferredBackupWindow'),
                VPCSecurityGroups=[Ref(RDS_SG_NAME % self.name), ]))

        endpoint = GetAtt(db_name, 'Endpoint.Address')

        # Setup CNAME to db
        t.add_resource(
            RecordSetType(
                '%sDnsRecord' % db_name,
                # Appends a '.' to the end of the domain
                HostedZoneId=Ref("InternalZoneId"),
                Comment='RDS DB CNAME Record',
                Name=Join(".", [Ref("InternalHostname"),
                          Ref("InternalZoneName")]),
                Type='CNAME',
                TTL='120',
                ResourceRecords=[endpoint],
                Condition="CreateInternalHostname"))
        t.add_output(Output('DBAddress', Value=endpoint))
        t.add_output(
            Output(
                'DBCname',
                Condition="CreateInternalHostname",
                Value=Ref("%sDnsRecord" % db_name)))

    def create_template(self):
        self.create_conditions()
        self.create_subnet_group()
        self.create_security_group()
        self.create_rds()
