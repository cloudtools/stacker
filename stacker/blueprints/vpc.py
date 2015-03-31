""" The 'base' cloudformation stack that builds out the virtual datacenter.

This includes the VPC, it's subnets, availability zones, etc.
"""

from collections import OrderedDict

from troposphere import Ref, Output, Join, FindInMap
from troposphere import ec2
import netaddr

from .base import Blueprint

NAT_INSTANCE_NAME = 'NatInstance%s'
GATEWAY = 'InternetGateway'
GW_ATTACH = 'GatewayAttach'


class VPC(Blueprint):
    PARAMETERS = {
        "InstanceType": {
            "type": "String",
            "description": "NAT EC2 instance type.",
            "default": "m3.medium"},
        "SshKeyName": {
            "type": "AWS::EC2::KeyPair::KeyName"},
        "BaseDomain": {
            "type": "String",
            "description": "Base domain for the stack."},
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

    def create_vpc(self):
        t = self.template
        vpc = t.add_resource(ec2.VPC(
            'VPC',
            CidrBlock=Ref("CidrBlock"), EnableDnsSupport=True,
            EnableDnsHostnames=True))

        # Just about everything needs this, so storing it on the object
        self.vpc_ref = Ref(vpc)
        t.add_output(Output("VpcId", Value=self.vpc_ref))

    def create_default_security_group(self):
        t = self.template
        self.default_sg = t.add_resource(ec2.SecurityGroup(
            'DefaultSG',
            VpcId=self.vpc_ref,
            GroupDescription='Default Security Group'))
        t.add_output(
            Output('DefaultSG',
                   Value=Ref(self.default_sg)))

    def create_dhcp_options(self):
        t = self.template
        dhcp_options = t.add_resource(ec2.DHCPOptions(
            'DHCPOptions',
            DomainName=Ref("BaseDomain"),
            DomainNameServers=['AmazonProvidedDNS', ]))
        t.add_resource(ec2.VPCDHCPOptionsAssociation(
            'DHCPAssociation',
            VpcId=self.vpc_ref,
            DhcpOptionsId=Ref(dhcp_options)))

    def create_gateway(self):
        t = self.template
        t.add_resource(ec2.InternetGateway(GATEWAY))
        t.add_resource(ec2.VPCGatewayAttachment(
            GW_ATTACH,
            VpcId=self.vpc_ref,
            InternetGatewayId=Ref(GATEWAY)))

    def create_network(self):
        t = self.template
        self.create_gateway()
        t.add_resource(ec2.NetworkAcl('DefaultACL',
                                      VpcId=self.vpc_ref))

        # Now create the subnets
        self.subnets = OrderedDict()
        self.subnets['public'] = []
        self.subnets['private'] = []
        networks = {'private': self.cidr_block.subnet(22)}
        # Give /24's to the public networks from the first /22
        networks['public'] = next(networks['private']).subnet(24)
        network_prefixes = []

        self.nat_sg = self.create_nat_security_groups()

        for _, subnet_type in enumerate(self.subnets):
            name_prefix = subnet_type.capitalize()
            for _, zone in enumerate(self.zones):
                name_suffix = zone[-1].upper()
                cidr_block = str(next(networks[subnet_type]))
                # Used by other templates to pick static IPs
                network_prefixes.append('.'.join(cidr_block.split('.')[:-1]))
                subnet = t.add_resource(ec2.Subnet(
                    '%sSubnet%s' % (name_prefix, name_suffix),
                    AvailabilityZone=zone,
                    VpcId=self.vpc_ref,
                    DependsOn=GW_ATTACH,
                    CidrBlock=cidr_block))
                self.subnets[subnet_type].append(subnet)
                route_table = t.add_resource(ec2.RouteTable(
                    "%sRouteTable%s" % (name_prefix, name_suffix),
                    VpcId=self.vpc_ref,
                    Tags=[ec2.Tag('type', subnet_type)]))

                t.add_resource(ec2.SubnetRouteTableAssociation(
                    "%sRouteTableAssociation%s" % (name_prefix, name_suffix),
                    SubnetId=Ref(subnet),
                    RouteTableId=Ref(route_table)))

                if subnet_type == 'public':
                    # the public subnets are where the NAT instances live,
                    # so their default route needs to go to the AWS
                    # Internet Gateway
                    t.add_resource(
                        ec2.Route("%sRoute%s" % (name_prefix, name_suffix),
                                  RouteTableId=Ref(route_table),
                                  DestinationCidrBlock='0.0.0.0/0',
                                  GatewayId=Ref(GATEWAY)))

                    self.create_nat_instance(zone, subnet)
                else:
                    # Private subnets are where actual instances will live
                    # so their gateway needs to be through the nat instances
                    t.add_resource(ec2.Route(
                        '%sRoute%s' % (name_prefix, name_suffix),
                        RouteTableId=Ref(route_table),
                        DestinationCidrBlock='0.0.0.0/0',
                        InstanceId=Ref(NAT_INSTANCE_NAME % name_suffix)))
            t.add_output(
                Output(
                    "%sSubnets" % name_prefix,
                    Value=Join(",",
                               [Ref(sn) for sn in self.subnets[subnet_type]])))
            t.add_output(
                Output("%sNetworkPrefixes" % name_prefix,
                       Value=Join(",", network_prefixes)))

    def create_nat_security_groups(self):
        t = self.template
        # First setup the NAT Security Group Rules
        nat_private_in_all_rule = ec2.SecurityGroupRule(
            IpProtocol='-1', FromPort='-1', ToPort='-1',
            SourceSecurityGroupId=Ref(self.default_sg))

        nat_public_out_all_rule = ec2.SecurityGroupRule(
            IpProtocol='-1', FromPort='-1', ToPort='-1', CidrIp='0.0.0.0/0')

        return t.add_resource(ec2.SecurityGroup(
            'NATSG',
            VpcId=self.vpc_ref,
            GroupDescription='NAT Instance Security Group',
            SecurityGroupIngress=[nat_private_in_all_rule],
            SecurityGroupEgress=[nat_public_out_all_rule, ]))

    def create_nat_instance(self, zone, subnet):
        t = self.template
        suffix = zone[-1].upper()
        nat_instance = t.add_resource(ec2.Instance(
            NAT_INSTANCE_NAME % suffix,
            ImageId=FindInMap('AmiMap', Ref("AWS::Region"), Ref("ImageName")),
            SecurityGroupIds=[Ref(self.default_sg), Ref(self.nat_sg)],
            SubnetId=Ref(subnet),
            InstanceType=Ref('InstanceType'),
            SourceDestCheck=False,
            KeyName=Ref('SshKeyName'),
            Tags=[ec2.Tag('Name', 'nat-gw%s' % suffix.lower())],
            DependsOn=GW_ATTACH))

        t.add_resource(ec2.EIP(
            'NATExternalIp%s' % suffix,
            Domain='vpc',
            InstanceId=Ref(nat_instance),
            DependsOn=GW_ATTACH))
        return nat_instance

    def create_template(self):
        self.cidr_block = netaddr.IPNetwork(
            self.context.parameters['CidrBlock'])
        self.zones = self.context.parameters['Zones']
        self.template.add_output(
            Output("AvailabilityZones",
                   Value=Join(",", self.zones)))
        self.create_vpc()
        self.create_default_security_group()
        self.create_dhcp_options()
        self.create_network()
