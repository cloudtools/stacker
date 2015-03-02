""" The 'base' cloudformation stack that builds out the virtual datacenter.

This includes the VPC, it's subnets, availability zones, etc.
"""

from collections import OrderedDict

from troposphere import Ref, Output, Join, FindInMap, Parameter
from troposphere import ec2
from troposphere.route53 import RecordSetType
import netaddr

from ..stack import StackTemplateBase

NAT_INSTANCE_NAME = "NatInstance%s"


class VPC(StackTemplateBase):
    def create_parameters(self):
        t = self.template
        t.add_parameter(
            Parameter("NatInstanceType",
                      Type="String"))
        t.add_parameter(
            Parameter("SshKeyName",
                      Type="AWS::EC2::KeyPair::KeyName"))

    def create_vpc(self):
        t = self.template
        vpc = t.add_resource(ec2.VPC(
            'VPC',
            CidrBlock=str(self.cidr_block), EnableDnsSupport=True,
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
            DomainName=self.config.get('base_domain', 'remind.com'),
            DomainNameServers=['AmazonProvidedDNS', ]))
        t.add_resource(ec2.VPCDHCPOptionsAssociation(
            'DHCPAssociation',
            VpcId=self.vpc_ref,
            DhcpOptionsId=Ref(dhcp_options)))

    def create_network(self):
        t = self.template
        # First create the gateway
        gateway = t.add_resource(
            ec2.InternetGateway('InternetGateway'))
        # Make this an instance variable because a lot of other stuff
        # has to depend on this in order to ensure the stack can delete
        # properly every time.
        self.gw_attach = t.add_resource(ec2.VPCGatewayAttachment(
            'GatewayAttach',
            VpcId=self.vpc_ref,
            InternetGatewayId=Ref(gateway)))

        # Create the default ACL
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

        for i, subnet_type in enumerate(self.subnets):
            name_prefix = subnet_type.capitalize()
            for z, zone in enumerate(self.zones):
                name_suffix = zone[-1].upper()
                cidr_block = str(next(networks[subnet_type]))
                # Used by other templates to pick static IPs
                network_prefixes.append('.'.join(cidr_block.split('.')[:-1]))
                subnet = t.add_resource(ec2.Subnet(
                    '%sSubnet%s' % (name_prefix, name_suffix),
                    AvailabilityZone=zone,
                    VpcId=self.vpc_ref,
                    DependsOn=self.gw_attach.title,
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
                                  GatewayId=Ref(gateway)))

                    self.create_nat_instance(zone, subnet)
                else:
                    # Private subnets are where actual instances will live
                    # so their gateway needs to be through the nat instances
                    nat_instance_name = NAT_INSTANCE_NAME % name_suffix
                    t.add_resource(
                        ec2.Route('%sRoute%s' % (name_prefix, name_suffix),
                                  RouteTableId=Ref(route_table),
                                  DestinationCidrBlock='0.0.0.0/0',
                                  InstanceId=Ref(nat_instance_name)))
            subnet_refs = [Ref(sn) for sn in self.subnets[subnet_type]]
            t.add_output(
                Output("%sSubnets" % name_prefix,
                       Value=Join(",", subnet_refs)))
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

        # XXX Need to update to specific IPs eventually.
        ssh_ingress_rule = ec2.SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='22',
            ToPort='22',
            CidrIp='0.0.0.0/0')

        return t.add_resource(ec2.SecurityGroup(
            'NATSG',
            VpcId=self.vpc_ref,
            GroupDescription='NAT Instance Security Group',
            SecurityGroupIngress=[ssh_ingress_rule, nat_private_in_all_rule],
            SecurityGroupEgress=[nat_public_out_all_rule, ]))

    def create_nat_instance(self, zone, subnet):
        t = self.template
        suffix = zone[-1].upper()
        nat_instance = t.add_resource(ec2.Instance(
            NAT_INSTANCE_NAME % suffix,
            ImageId=FindInMap('AmiMap', Ref("AWS::Region"), 'NAT'),
            SecurityGroupIds=[Ref(self.default_sg), Ref(self.nat_sg)],
            SubnetId=Ref(subnet),
            InstanceType=Ref('NatInstanceType'),
            SourceDestCheck=False,
            KeyName=Ref('SshKeyName'),
            Tags=[ec2.Tag('Name', 'nat-gw%s' % suffix.lower())],
            DependsOn=self.gw_attach.title))

        eip = t.add_resource(ec2.EIP(
            'NATExternalIp%s' % suffix,
            Domain='vpc',
            InstanceId=Ref(nat_instance),
            DependsOn=self.gw_attach.title))
        self.create_nat_dns(zone, eip)
        return nat_instance

    def create_nat_dns(self, zone, ip):
        base_domain = self.config.get('base_domain', 'remind.com')
        t = self.template
        suffix = zone[-1].upper()
        return t.add_resource(RecordSetType(
            "NatEIPDNS%s" % suffix,
            HostedZoneName=base_domain + '.',
            Comment='NAT gateway A record.',
            Name="gw%s.%s" % (suffix, 'int.' + base_domain),
            Type='A',
            TTL='120',
            ResourceRecords=[Ref(ip)]))

    def create_template(self):
        self.cidr_block = netaddr.IPNetwork(
            self.config.get('cidr_block', '10.128.0.0/16'))
        self.zones = self.config['zones']
        self.template.add_output(
            Output("AvailabilityZones",
                   Value=Join(",", self.zones)))
        self.create_parameters()
        self.create_vpc()
        self.create_default_security_group()
        self.create_dhcp_options()
        self.create_network()
