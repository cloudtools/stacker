

class TroposphereType(object):

    def __init__(self, defined_type, many=False, optional=False,
                 validate=True):
        """Represents a Troposphere type.

        :class:`Troposphere` will convert the value provided to the variable to
        the specified Troposphere type.

        Both resource and parameter classes (which are just used to configure
        other resources) are acceptable as configuration values.

        Complete resource definitions must be dictionaries, with the keys
        identifying the resource titles, and the values being used as the
        constructor parameters.

        Parameter classes can be defined as dictionariy or a list of
        dictionaries. In either case, the keys and values will be used directly
        as constructor parameters.

        Args:
            defined_type (type): Troposphere type
            many (bool): Whether or not multiple resources can be constructed.
                If the defined type is a resource, multiple resources can be
                passed as a dictionary of dictionaries.
                If it is a parameter class, multiple resources are passed as
                a list.
            optional (bool): Whether an undefined/null configured value is
                acceptable. In that case a value of ``None`` will be passed to
                the template, even if ``many`` is enabled.
            validate (bool): Whether to validate the generated object on
                creation. Should be left enabled unless the object will be
                augmented with mandatory parameters in the template code, such
                that it must be validated at a later point.

        """

        self._validate_type(defined_type)

        self._type = defined_type
        self._many = many
        self._optional = optional
        self._validate = validate

    def _validate_type(self, defined_type):
        if not hasattr(defined_type, "from_dict"):
            raise ValueError("Type must have `from_dict` attribute")

    @property
    def resource_name(self):
        return (getattr(self._type, 'resource_name', None)
                or self._type.__name__)

    def create(self, value):
        """Create the troposphere type from the value.

        Args:
            value (Union[dict, list]): A dictionary or list of dictionaries
                (see class documentation for details) to use as parameters to
                create the Troposphere type instance.
                Each dictionary will be passed to the `from_dict` method of the
                type.

        Returns:
            Union[list, type]: Returns the value converted to the troposphere
                type

        """

        # Explicitly check with len such that non-sequence types throw.
        if self._optional and (value is None or len(value) == 0):
            return None

        if hasattr(self._type, 'resource_type'):
            # Our type is a resource, so ensure we have a dict of title to
            # parameters
            if not isinstance(value, dict):
                raise ValueError("Resources must be specified as a dict of "
                                 "title to parameters")
            if not self._many and len(value) > 1:
                raise ValueError("Only one resource can be provided for this "
                                 "TroposphereType variable")

            result = [self._type.from_dict(title, v) for title, v in
                      value.items()]
        else:
            # Our type is for properties, not a resource, so don't use
            # titles
            if self._many:
                result = [self._type.from_dict(None, v) for v in value]
            elif not isinstance(value, dict):
                raise ValueError("TroposphereType for a single non-resource"
                                 "type must be specified as a dict of "
                                 "parameters")
            else:
                result = [self._type.from_dict(None, value)]

        if self._validate:
            for v in result:
                v._validate_props()

        return result[0] if not self._many else result


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
