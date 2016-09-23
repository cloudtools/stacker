from stacker.blueprints.base import Blueprint
from stacker.blueprints.variables.types import (
    CFNCommaDelimitedList,
    CFNNumber,
    CFNString,
    EC2KeyPairKeyName,
    EC2SecurityGroupId,
    EC2SubnetIdList,
    EC2VPCId,
)


class VPC(Blueprint):
    VARIABLES = {
        "AZCount": {
            "type": int,
            "default": 2,
        },
        "PrivateSubnets": {
            "type": CFNCommaDelimitedList,
            "description": "Comma separated list of subnets to use for "
                           "non-public hosts. NOTE: Must have as many subnets "
                           "as AZCount"},
        "PublicSubnets": {
            "type": CFNCommaDelimitedList,
            "description": "Comma separated list of subnets to use for "
                           "public hosts. NOTE: Must have as many subnets "
                           "as AZCount"},
        "InstanceType": {
            "type": CFNString,
            "description": "NAT EC2 instance type.",
            "default": "m3.medium"},
        "SshKeyName": {
            "type": EC2KeyPairKeyName},
        "BaseDomain": {
            "type": CFNString,
            "default": "",
            "description": "Base domain for the stack."},
        "InternalDomain": {
            "type": CFNString,
            "default": "",
            "description": "Internal domain name, if you have one."},
        "CidrBlock": {
            "type": CFNString,
            "description": "Base CIDR block for subnets.",
            "default": "10.128.0.0/16"},
        "ImageName": {
            "type": CFNString,
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "NAT"},
        "UseNatGateway": {
            "type": CFNString,
            "allowed_values": ["true", "false"],
            "description": "If set to true, will configure a NAT Gateway"
                           "instead of NAT instances.",
            "default": "false"},
    }

    def create_template(self):
        return


class Bastion(Blueprint):
    VARIABLES = {
        "VpcId": {"type": EC2VPCId, "description": "Vpc Id"},
        "DefaultSG": {"type": EC2SecurityGroupId,
                      "description": "Top level security group."},
        "PublicSubnets": {"type": EC2SubnetIdList,
                          "description": "Subnets to deploy public "
                                         "instances in."},
        "PrivateSubnets": {"type": EC2SubnetIdList,
                           "description": "Subnets to deploy private "
                                          "instances in."},
        "AvailabilityZones": {"type": CFNCommaDelimitedList,
                              "description": "Availability Zones to deploy "
                                             "instances in."},
        "InstanceType": {"type": CFNString,
                         "description": "EC2 Instance Type",
                         "default": "m3.medium"},
        "MinSize": {"type": CFNNumber,
                    "description": "Minimum # of instances.",
                    "default": "1"},
        "MaxSize": {"type": CFNNumber,
                    "description": "Maximum # of instances.",
                    "default": "5"},
        "SshKeyName": {"type": EC2KeyPairKeyName},
        "OfficeNetwork": {
            "type": CFNString,
            "description": "CIDR block allowed to connect to bastion hosts."},
        "ImageName": {
            "type": CFNString,
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "bastion"},
    }

    def create_template(self):
        return
