

class TroposphereType(object):

    def __init__(self, defined_type, resource_name=None):
        """Represents a Troposphere type.

        :class:`TroposphereType` will convert the value for the variable to the
        given Troposphere type.

        Args:
            defined_type (Union[list, type]): List of or single Troposphere
                type
            resource_name (str): The name to use for the resource when creating
                the type. If nothing is provided, the class name of the type
                will be used.

        """
        self.type = defined_type
        is_list = isinstance(self.type, list)
        if is_list:
            if len(self.type) > 1:
                raise ValueError(
                    "TroposphereType only supports lists of one type")
            elif not len(self.type):
                raise ValueError("Misisng required type for list")
            self._validate_type(self.type[0])
        else:
            self._validate_type(self.type)

        if resource_name is None:
            if is_list:
                resource_name = self.type[0].__name__
            else:
                resource_name = self.type.__name__

        self.resource_name = resource_name

    def _validate_type(self, defined_type):
        if not hasattr(defined_type, "from_dict"):
            raise ValueError("Type must have `from_dict` attribute")

    def create(self, value):
        """Create the troposphere type from the value.

        Args:
            value (Union[list, dict]): either a list of dictionaries or a
                single dictionary we want to convert to the specified
                troposphere type.

        Returns:
            Union[list, type]: Returns the value converted to the troposphere
                type

        """
        if isinstance(value, list):
            new_type = self.type[0]
            output = []
            for index, v in enumerate(value):
                name = "{}{}".format(self.resource_name, index + 1)
                output.append(new_type.from_dict(name, v))
        else:
            output = self.type.from_dict(self.resource_name, value)
        return output


class CFNType(object):

    def __init__(self, parameter_type):
        """Represents a CloudFormation Parameter Type.

        :class:`CFNType`` can be used as the `type` for a Blueprint variable.
        Unlike other variables, a variable with `type` :class:`CFNType`, will
        be submitted to CloudFormation as a Parameter.

        Args:
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
