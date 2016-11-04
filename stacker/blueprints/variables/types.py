

class CFNType(object):

    def __init__(self, parameter_type):
        """Represents a CloudFormation Parameter Type.

        :class`CFNType`` can be used as the `type` for a Blueprint variable.
        Unlike other variables, a variable with `type` :class:`CFNType`, will
        be submitted to CloudFormation as a Parameter.

        Arguments:
            parameter_type (str): An AWS specific parameter type
                (http://goo.gl/PthovJ)

        """
        self.parameter_type = parameter_type

CFNString = CFNType("String")
CFNNumber = CFNType("Number")
CFNNumberList = CFNType("List<Number>")
CFNCommaDelimitedList = CFNType("CommaDelimitedList")
EC2AvailabilityZoneName = CFNType("AWS::EC2::AvailabilityZone::Name")
EC2ImageId = CFNType("AWS::EC2::Image::Id")
EC2InstanceId = CFNType("AWS::EC2::Instance::Id")
EC2KeyPairKeyName = CFNType("AWS::EC2::KeyPair::KeyName")
EC2SecurityGroupGroupName = CFNType("AWS::EC2::SecurityGroup::GroupName")
EC2SecurityGroupId = CFNType("AWS::EC2::SecurityGroup::Id")
EC2SubnetId = CFNType("AWS::EC2::Subnet::Id")
EC2VolumeId = CFNType("AWS::EC2::Volume::Id")
EC2VPCId = CFNType("AWS::EC2::VPC::Id")
Route53HostedZoneId = CFNType("AWS::Route53::HostedZone::Id")
EC2AvailabilityZoneNameList = CFNType("List<AWS::EC2::AvailabilityZone::Name>")
EC2ImageIdList = CFNType("List<AWS::EC2::Image::Id>")
EC2InstanceIdList = CFNType("List<AWS::EC2::Instance::Id>")
EC2SecurityGroupGroupNameList = CFNType(
    "List<AWS::EC2::SecurityGroup::GroupName>")
EC2SecurityGroupIdList = CFNType("List<AWS::EC2::SecurityGroup::Id>")
EC2SubnetIdList = CFNType("List<AWS::EC2::Subnet::Id>")
EC2VolumeIdList = CFNType("List<AWS::EC2::Volume::Id>")
EC2VPCIdList = CFNType("List<AWS::EC2::VPC::Id>")
Route53HostedZoneIdList = CFNType("List<AWS::Route53::HostedZone::Id>")
