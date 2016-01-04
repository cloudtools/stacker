""" The 'base' cloudformation stack that builds out the virtual datacenter.

This includes the VPC, it's subnets, availability zones, etc.
"""
import warnings

warnings.warn("The included blueprints are deprecated. You should install "
              "the `stacker_blueprints` module instead.",
              DeprecationWarning)

from troposphere import (
    Ref, Output, Join, FindInMap, Select, GetAZs, Not, Equals, Tags, Or,
    Condition
)
from troposphere import ec2
from troposphere.route53 import HostedZone, HostedZoneVPCs

from .base import Blueprint

NAT_INSTANCE_NAME = 'NatInstance%s'
GATEWAY = 'InternetGateway'
GW_ATTACH = 'GatewayAttach'
VPC_NAME = "VPC"
VPC_ID = Ref(VPC_NAME)
DEFAULT_SG = "DefaultSG"
NAT_SG = "NATSG"


class VPC(Blueprint):
    LOCAL_PARAMETERS = {
        "AZCount":  {
            "type": int,
            "default": 2,
        }
    }

    PARAMETERS = {
        "PrivateSubnets": {
            "type": "CommaDelimitedList",
            "description": "Comma separated list of subnets to use for "
                           "non-public hosts. NOTE: Must have as many subnets "
                           "as AZCount"},
        "PublicSubnets": {
            "type": "CommaDelimitedList",
            "description": "Comma separated list of subnets to use for "
                           "public hosts. NOTE: Must have as many subnets "
                           "as AZCount"},
        "InstanceType": {
            "type": "String",
            "description": "NAT EC2 instance type.",
            "default": "m3.medium"},
        "SshKeyName": {
            "type": "AWS::EC2::KeyPair::KeyName"},
        "BaseDomain": {
            "type": "String",
            "default": "",
            "description": "Base domain for the stack."},
        "InternalDomain": {
            "type": "String",
            "default": "",
            "description": "Internal domain name, if you have one."},
        "CidrBlock": {
            "type": "String",
            "description": "Base CIDR block for subnets.",
            "default": "10.128.0.0/16"},
        "ImageName": {
            "type": "String",
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "NAT"},
    }

    def create_conditions(self):
        self.template.add_condition(
            "HasInternalDomain",
            Not(Equals(Ref("InternalDomain"), "")))
        self.template.add_condition(
            "HasExternalDomain",
            Not(Equals(Ref("BaseDomain"), "")))
        self.template.add_condition(
            "HasHostedZones",
            Or(
                Condition("HasInternalDomain"),
                Condition("HasExternalDomain")
            ))
        self.template.add_condition(
            "NoHostedZones",
            Not(Condition("HasHostedZones")))

    def create_vpc(self):
        t = self.template
        t.add_resource(ec2.VPC(
            VPC_NAME,
            CidrBlock=Ref("CidrBlock"), EnableDnsSupport=True,
            EnableDnsHostnames=True))

        # Just about everything needs this, so storing it on the object
        t.add_output(Output("VpcId", Value=VPC_ID))

    def create_internal_zone(self):
        t = self.template
        t.add_resource(
            HostedZone(
                "InternalZone",
                Name=Ref("InternalDomain"),
                VPCs=[HostedZoneVPCs(
                    VPCId=VPC_ID,
                    VPCRegion=Ref("AWS::Region"))],
                Condition="HasInternalDomain"))
        t.add_output(
            Output(
                "InternalZoneId",
                Value=Ref("InternalZone"),
                Condition="HasInternalDomain"))
        t.add_output(
            Output(
                "InternalZoneName",
                Value=Ref("InternalDomain"),
                Condition="HasInternalDomain"))

    def create_default_security_group(self):
        t = self.template
        t.add_resource(ec2.SecurityGroup(
            DEFAULT_SG,
            VpcId=VPC_ID,
            GroupDescription='Default Security Group'))
        t.add_output(
            Output('DefaultSG',
                   Value=Ref(DEFAULT_SG)))

    def _dhcp_options_hosted_zones(self):
        t = self.template
        domain_name = Join(" ", [Ref("BaseDomain"), Ref("InternalDomain")])
        dhcp_options = t.add_resource(ec2.DHCPOptions(
            'DHCPOptionsWithDNS',
            DomainName=domain_name,
            DomainNameServers=['AmazonProvidedDNS', ],
            Condition="HasHostedZones"))
        t.add_resource(ec2.VPCDHCPOptionsAssociation(
            'DHCPAssociationWithDNS',
            VpcId=VPC_ID,
            DhcpOptionsId=Ref(dhcp_options),
            Condition="HasHostedZones"))

    def _dhcp_options_no_hosted_zones(self):
        t = self.template
        dhcp_options = t.add_resource(ec2.DHCPOptions(
            'DHCPOptionsNoDNS',
            DomainNameServers=['AmazonProvidedDNS', ],
            Condition="NoHostedZones"))
        t.add_resource(ec2.VPCDHCPOptionsAssociation(
            'DHCPAssociationNoDNS',
            VpcId=VPC_ID,
            DhcpOptionsId=Ref(dhcp_options),
            Condition="NoHostedZones"))

    def create_dhcp_options(self):
        self._dhcp_options_hosted_zones()
        self._dhcp_options_no_hosted_zones()

    def create_gateway(self):
        t = self.template
        t.add_resource(ec2.InternetGateway(GATEWAY))
        t.add_resource(ec2.VPCGatewayAttachment(
            GW_ATTACH,
            VpcId=VPC_ID,
            InternetGatewayId=Ref(GATEWAY)))

    def create_network(self):
        t = self.template
        self.create_gateway()
        vpc_id = Ref("VPC")
        t.add_resource(ec2.NetworkAcl('DefaultACL',
                                      VpcId=vpc_id))

        self.create_nat_security_groups()
        subnets = {'public': [], 'private': []}
        net_types = subnets.keys()
        zones = []
        for i in range(self.local_parameters["AZCount"]):
            az = Select(i, GetAZs(""))
            zones.append(az)
            name_suffix = i
            for net_type in net_types:
                name_prefix = net_type.capitalize()
                subnet_name = "%sSubnet%s" % (name_prefix, name_suffix)
                subnets[net_type].append(subnet_name)
                t.add_resource(ec2.Subnet(
                    subnet_name,
                    AvailabilityZone=az,
                    VpcId=vpc_id,
                    DependsOn=GW_ATTACH,
                    CidrBlock=Select(i, Ref("%sSubnets" % name_prefix)),
                    Tags=Tags(type=net_type)))
                route_table_name = "%sRouteTable%s" % (name_prefix,
                                                       name_suffix)
                t.add_resource(ec2.RouteTable(
                    route_table_name,
                    VpcId=vpc_id,
                    Tags=[ec2.Tag('type', net_type)]))
                t.add_resource(ec2.SubnetRouteTableAssociation(
                    "%sRouteTableAssociation%s" % (name_prefix, name_suffix),
                    SubnetId=Ref(subnet_name),
                    RouteTableId=Ref(route_table_name)))
                if net_type == 'public':
                    # the public subnets are where the NAT instances live,
                    # so their default route needs to go to the AWS
                    # Internet Gateway
                    t.add_resource(ec2.Route(
                        "%sRoute%s" % (name_prefix, name_suffix),
                        RouteTableId=Ref(route_table_name),
                        DestinationCidrBlock="0.0.0.0/0",
                        GatewayId=Ref(GATEWAY)))
                    self.create_nat_instance(i, subnet_name)
                else:
                    # Private subnets are where actual instances will live
                    # so their gateway needs to be through the nat instances
                    t.add_resource(ec2.Route(
                        '%sRoute%s' % (name_prefix, name_suffix),
                        RouteTableId=Ref(route_table_name),
                        DestinationCidrBlock='0.0.0.0/0',
                        InstanceId=Ref(NAT_INSTANCE_NAME % name_suffix)))
        for net_type in net_types:
            t.add_output(Output(
                "%sSubnets" % net_type.capitalize(),
                Value=Join(",",
                           [Ref(sn) for sn in subnets[net_type]])))
        self.template.add_output(Output(
            "AvailabilityZones",
            Value=Join(",", zones)))

    def create_nat_security_groups(self):
        t = self.template
        # First setup the NAT Security Group Rules
        nat_private_in_all_rule = ec2.SecurityGroupRule(
            IpProtocol='-1', FromPort='-1', ToPort='-1',
            SourceSecurityGroupId=Ref(DEFAULT_SG))

        nat_public_out_all_rule = ec2.SecurityGroupRule(
            IpProtocol='-1', FromPort='-1', ToPort='-1', CidrIp='0.0.0.0/0')

        return t.add_resource(ec2.SecurityGroup(
            NAT_SG,
            VpcId=VPC_ID,
            GroupDescription='NAT Instance Security Group',
            SecurityGroupIngress=[nat_private_in_all_rule],
            SecurityGroupEgress=[nat_public_out_all_rule, ]))

    def create_nat_instance(self, zone_id, subnet_name):
        t = self.template
        suffix = zone_id
        nat_instance = t.add_resource(ec2.Instance(
            NAT_INSTANCE_NAME % suffix,
            ImageId=FindInMap('AmiMap', Ref("AWS::Region"), Ref("ImageName")),
            SecurityGroupIds=[Ref(DEFAULT_SG), Ref(NAT_SG)],
            SubnetId=Ref(subnet_name),
            InstanceType=Ref('InstanceType'),
            SourceDestCheck=False,
            KeyName=Ref('SshKeyName'),
            Tags=[ec2.Tag('Name', 'nat-gw%s' % suffix)],
            DependsOn=GW_ATTACH))

        t.add_resource(ec2.EIP(
            'NATExternalIp%s' % suffix,
            Domain='vpc',
            InstanceId=Ref(nat_instance),
            DependsOn=GW_ATTACH))
        return nat_instance

    def create_template(self):
        self.create_conditions()
        self.create_vpc()
        self.create_internal_zone()
        self.create_default_security_group()
        self.create_dhcp_options()
        self.create_network()
