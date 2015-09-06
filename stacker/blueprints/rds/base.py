from troposphere import (
    Ref, ec2, Output, GetAtt, Not, Equals, Condition, And, Join, If, FindInMap,
    Tags
)
from troposphere.rds import (
    DBInstance, DBSubnetGroup, DBParameterGroup, OptionGroup,
)
from troposphere.route53 import RecordSetType

from ..base import Blueprint
from .mappings import MAPPINGS

RDS_ENGINES = ["MySQL", "oracle-se1", "oracle-se", "oracle-ee", "sqlserver-ee",
               "sqlserver-se", "sqlserver-ex", "sqlserver-web", "postgres"]

# Resource name constants
SUBNET_GROUP = "RDSSubnetGroup"
SECURITY_GROUP = "RDSSecurityGroup"
DBINSTANCE_NO_IOPS = "RDSDBInstanceNoIops"
DBINSTANCE_WITH_IOPS = "RDSDBInstanceWithIops"
DNS_RECORD = "DBInstanceDnsRecord"


def common_parameters():
    """ Return common parameters for all RDS stacks.

    Returns:
        dict: A dictionary of parameter definitions.
    """

    parameters = {
        "VpcId": {
            "type": "AWS::EC2::VPC::Id",
            "description": "Vpc Id"},
        "Subnets": {
            "type": "List<AWS::EC2::Subnet::Id>",
            "description": "Subnets to deploy RDS instance in."},
        "InstanceType": {
            "type": "String",
            "description": "AWS RDS Instance Type",
            "default": "db.m3.large"},
        "AllowMajorVersionUpgrade": {
            "type": "String",
            "description": "Set to 'true' to allow major version "
                           "upgrades.",
            "default": "false",
            "allowed_values": ["true", "false"]
        },
        "AutoMinorVersionUpgrade": {
            "type": "String",
            "description": "Set to 'true' to allow minor version upgrades "
                           "during maintenance windows.",
            "default": "false",
            "allowed_values": ["true", "false"]
        },
        "AllocatedStorage": {
            "type": "Number",
            "description": "Space, in GB, to allocate to RDS instance. If "
                           "IOPS is set below, this must be a minimum of "
                           "100 and must be at least 1/10th the IOPs "
                           "setting.",
            "default": "10"},
        "IOPS": {
            "type": "Number",
            "description": "If set, uses provisioned IOPS for the "
                           "database. Note: This must be no more than "
                           "10x of AllocatedStorage. Minimum: 1000",
            "max_value": 10000,
            "default": "0"},
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
        "PreferredMaintenanceWindow": {
            "type": "String",
            "description": "A (minimum 30 minute) window in "
                           "DDD:HH:MM-DDD:HH:MM format in UTC for backups. "
                           "Default: Sunday 3am-4am PST",
            "default": "Sun:11:00-Sun:12:00"},

    }

    return parameters


class MasterInstance(Blueprint):
    """ Blueprint for a generic Master RDS Database Instance.

    Subclasses should be created for each RDS engine for better validation of
    things like engine version.
    """

    ENGINE = None
    LOCAL_PARAMETERS = {
        "DatabaseParameters": {
            "type": dict,
            "default": {},
        },
    }

    def get_engine_versions(self):
        """Used by engine specific subclasses - returns valid engine versions.

        Should only be overridden if the class variable ENGINE is defined on
        the class.

        Return:
            list: A list of valid engine versions for the given engine.
        """
        return []

    def _get_parameters(self):
        master_parameters = {
            "EngineVersion": {
                "type": "String",
                "description": "Database engine version for the RDS Instance.",
            },
            "BackupRetentionPeriod": {
                "type": "Number",
                "description": "Number of days to retain database backups.",
                "min_value": 0,
                "default": 7,
                "max_value": 35,
                "constraint_description": "Must be between 0-35.",
            },
            "MasterUser": {
                "type": "String",
                "description": "Name of the master user in the db.",
                "default": "dbuser"},
            "MasterUserPassword": {
                "type": "String",
                "no_echo": "true",
                "description": "Master user password."},
            "PreferredBackupWindow": {
                "type": "String",
                "description": "A (minimum 30 minute) window in HH:MM-HH:MM "
                               "format in UTC for backups. Default: 3am-4am "
                               "PST",
                "default": "11:00-12:00"},
            "DatabaseName": {
                "type": "String",
                "description": "Initial db to create in database."},
            "MultiAZ": {
                "type": "String",
                "description": "Set to 'false' to disable MultiAZ support.",
                "default": "true"},
            "StorageEncrypted": {
                "type": "String",
                "description": "Set to 'false' to disable encrypted storage.",
                "default": "true",
                "allowed_values": ["true", "false"]
            },
            "KmsKeyid": {
                "type": "String",
                "description": "Requires that StorageEncrypted is true. "
                               "Should be an ARN to the KMS key that should "
                               "be used to encrypt the storage.",
                "default": "",
            },
            "LicenseModel": {
                "type": "String",
                "description": "License model for the database instance.",
                "default": "general-public-license",
                "allowed_values": ["general-public-license",
                                   "license-included",
                                   "bring-your-own-license"]
            },
        }
        engine_versions = self.get_engine_versions()
        if engine_versions:
            master_parameters['EngineVersion']['allowed_values'] = \
                engine_versions

        if not self.ENGINE:
            master_parameters['Engine'] = {
                "type": "String",
                "description": "Database engine for the RDS Instance.",
                "allowed_values": RDS_ENGINES
            }
        else:
            if self.ENGINE not in RDS_ENGINES:
                raise ValueError("ENGINE must be one of: %s" %
                                 ", ".join(RDS_ENGINES))

        # Merge common parameters w/ master only parameters
        parameters = common_parameters().update(master_parameters)

        return parameters

    def family_mappings(self):
        t = self.template
        for name, mapping in MAPPINGS:
            t.add_mapping(name, mapping)

    def create_conditions(self):
        t = self.template
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
        t.add_condition(
            "ProvisionedIOPS",
            Not(Equals(Ref("IOPS"), "0")))
        t.add_condition(
            "NoProvisionedIOPS",
            Equals(Ref("IOPS"), "0"))

    def create_subnet_group(self):
        t = self.template
        t.add_resource(
            DBSubnetGroup(
                SUBNET_GROUP,
                DBSubnetGroupDescription="%s VPC subnet group." % self.name,
                SubnetIds=Ref("Subnets")))

    def create_security_group(self):
        t = self.template
        sg = t.add_resource(
            ec2.SecurityGroup(
                SECURITY_GROUP,
                GroupDescription="%s RDS security group" % self.name,
                VpcId=Ref("VpcId")))
        t.add_output(Output("SecurityGroup", Value=Ref(sg)))

    def get_db_instance(self):
        return If("ProvisionedIOPS", DBINSTANCE_WITH_IOPS,
                  DBINSTANCE_NO_IOPS)

    def get_db_endpoint(self):
        endpoint = GetAtt(self.get_db_instance(), "Endpoint.Address")
        return endpoint

    def get_common_attrs(self):
        return {
            "AllocatedStorage": Ref("AllocatedStorage"),
            "AllowMajorVersionUpgrade": Ref("AllowMajorVersionUpgrade"),
            "AutoMinorVersionUpgrade": Ref("AutoMinorVersionUpgrade"),
            "BackupRetentionPeriod": Ref("BackupRetentionPeriod"),
            "DBName": Ref("DatabaseName"),
            "DBInstanceClass": Ref("InstanceType"),
            "DBParameterGroupName": Ref("ParameterGroup"),
            "DBSubnetGroupName": Ref(SUBNET_GROUP),
            "Engine": self.ENGINE or Ref("Engine"),
            "EngineVersion": Ref("EngineVersion"),
            "LicenseModel": Ref("LicenseModel"),
            "MasterUsername": Ref("MasterUser"),
            "MasterUserPassword": Ref("MasterUserPassword"),
            "MultiAZ": Ref("MultiAZ"),
            "OptionGroupName": Ref("OptionGroup"),
            "PreferredBackupWindow": Ref("PreferredBackupWindow"),
            "PreferredMaintenanceWindow": Ref("PreferredMaintenanceWindow"),
            "StorageEncrypted": Ref("StorageEncrypted"),
            "VPCSecurityGroups": [Ref(SECURITY_GROUP), ],
            "Tags": Tags(Name=self.name),
        }

    def create_parameter_group(self):
        t = self.template
        params = self.local_parameters["DatabaseParameters"]
        engine = self.ENGINE or Ref("Engine")
        t.add_resource(
            DBParameterGroup(
                "ParameterGroup",
                Description=self.name,
                Family=FindInMap("DBFamily", engine, Ref("EngineVersion")),
                Parameters=params,
            )
        )

    def get_option_configurations(self):
        options = []
        return options

    def create_option_group(self):
        t = self.template
        engine = self.ENGINE or Ref("Engine")
        t.add_resource(
            OptionGroup(
                "OptionGroup",
                EngineName=Ref("Engine"),
                MajorEngineVersion=FindInMap("MajorVersions",
                                             engine, Ref("EngineVersion")),
                OptionGroupDescription=self.name,
                OptionConfigurations=self.get_option_configurations(),
            )
        )

    def create_rds(self):
        t = self.template
        t.add_resource(
            DBInstance(
                DBINSTANCE_NO_IOPS,
                Condition="NoProvisionedIOPS",
                **self.get_common_attrs()
                ))

        t.add_resource(
            DBInstance(
                DBINSTANCE_WITH_IOPS,
                Condition="ProvisionedIOPS",
                StorageType="io1",
                Iops=Ref("IOPS"),
                **self.get_common_attrs()
                ))

    def create_dns_records(self):
        t = self.template
        endpoint = self.get_db_endpoint()

        # Setup CNAME to db
        t.add_resource(
            RecordSetType(
                DNS_RECORD,
                # Appends a "." to the end of the domain
                HostedZoneId=Ref("InternalZoneId"),
                Comment="RDS DB CNAME Record",
                Name=Join(".", [Ref("InternalHostname"),
                          Ref("InternalZoneName")]),
                Type="CNAME",
                TTL="120",
                ResourceRecords=[endpoint],
                Condition="CreateInternalHostname"))

    def create_db_outputs(self):
        t = self.template
        t.add_output(Output("DBAddress", Value=self.get_db_endpoint()))
        t.add_output(Output("DBInstance", Value=Ref(self.get_db_instance())))
        t.add_output(
            Output(
                "DBCname",
                Condition="CreateInternalHostname",
                Value=Ref(DNS_RECORD)))

    def create_template(self):
        self.create_conditions()
        self.family_mappings()
        self.create_parameter_group()
        self.create_option_group()
        self.create_subnet_group()
        self.create_security_group()
        self.create_rds()
        self.create_dns_records()
        self.create_db_outputs()


class ReadReplica(MasterInstance):
    """ Blueprint for a Read replica RDS Database Instance. """
    def _get_parameters(self):
        parameters = common_parameters()
        parameters['MasterDatabaseId'] = {
            "type": "String",
            "description": "ID of the master database to create a read "
                           "replica of."}
        return parameters

    def get_common_attrs(self):
        return {
            "SourceDBInstanceIdentifier": Ref("MasterDatabaseId"),
            "AllocatedStorage": Ref("AllocatedStorage"),
            "AllowMajorVersionUpgrade": Ref("AllowMajorVersionUpgrade"),
            "AutoMinorVersionUpgrade": Ref("AutoMinorVersionUpgrade"),
            "DBInstanceClass": Ref("InstanceType"),
            "DBSubnetGroupName": Ref(SUBNET_GROUP),
            "OptionGroupName": Ref("OptionGroup"),
            "PreferredMaintenanceWindow": Ref("PreferredMaintenanceWindow"),
            "VPCSecurityGroups": [Ref(SECURITY_GROUP), ],
        }

    def create_rds(self):
        t = self.template
        # Non-provisioned iops database
        t.add_resource(
            DBInstance(
                DBINSTANCE_NO_IOPS,
                Condition="NoProvisionedIOPS",
                **self.get_common_attrs()
            ))

        t.add_resource(
            DBInstance(
                DBINSTANCE_WITH_IOPS,
                Condition="ProvisionedIOPS",
                StorageType="io1",
                Iops=Ref("IOPS"),
                **self.get_common_attrs()
            ))

        t.add_output(Output("DBAddress", Value=self.get_db_endpoint()))
