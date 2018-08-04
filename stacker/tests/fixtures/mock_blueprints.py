from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import range
from troposphere import GetAtt, Output, Sub, Ref
from troposphere import iam

from awacs.aws import Policy, Statement, AWSPrincipal
import awacs
import awacs.s3
import awacs.cloudformation
import awacs.iam
import awacs.sts

from troposphere.cloudformation import WaitCondition, WaitConditionHandle

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


class FunctionalTests(Blueprint):
    """This creates a stack with an IAM user and access key for running the
    functional tests for stacker.
    """

    VARIABLES = {
        "StackerNamespace": {
            "type": CFNString,
            "description": "The stacker namespace that the tests will use. "
                           "Access to cloudformation will be restricted to "
                           "only allow access to stacks with this prefix."},
        "StackerBucket": {
            "type": CFNString,
            "description": "The name of the bucket that the tests will use "
                           "for uploading templates."}
    }

    def create_template(self):
        t = self.template

        bucket_arn = Sub("arn:aws:s3:::${StackerBucket}*")
        objects_arn = Sub("arn:aws:s3:::${StackerBucket}*/*")
        cloudformation_scope = Sub(
            "arn:aws:cloudformation:*:${AWS::AccountId}:"
            "stack/${StackerNamespace}-*")
        changeset_scope = "*"

        # This represents the precise IAM permissions that stacker itself
        # needs.
        stacker_policy = iam.Policy(
            PolicyName="Stacker",
            PolicyDocument=Policy(
                Statement=[
                    Statement(
                        Effect="Allow",
                        Resource=["*"],
                        Action=[awacs.s3.ListAllMyBuckets]
                    ),
                    Statement(
                        Effect="Allow",
                        Resource=[bucket_arn],
                        Action=[
                            awacs.s3.ListBucket,
                            awacs.s3.GetBucketLocation,
                            awacs.s3.CreateBucket,
                            awacs.s3.DeleteBucket,
                        ]
                    ),
                    Statement(
                        Effect="Allow",
                        Resource=[bucket_arn],
                        Action=[
                            awacs.s3.GetObject,
                            awacs.s3.GetObjectAcl,
                            awacs.s3.PutObject,
                            awacs.s3.PutObjectAcl,
                        ]
                    ),
                    Statement(
                        Effect="Allow",
                        Resource=[objects_arn],
                        Action=[
                            awacs.s3.DeleteObject,
                        ]
                    ),
                    Statement(
                        Effect="Allow",
                        Resource=[changeset_scope],
                        Action=[
                            awacs.cloudformation.DescribeChangeSet,
                            awacs.cloudformation.ExecuteChangeSet,
                            awacs.cloudformation.DeleteChangeSet,
                        ]
                    ),
                    Statement(
                        Effect="Deny",
                        Resource=[Ref("AWS::StackId")],
                        Action=[awacs.cloudformation.Action("*")]
                    ),
                    Statement(
                        Effect="Allow",
                        Resource=[cloudformation_scope],
                        Action=[
                            awacs.cloudformation.GetTemplate,
                            awacs.cloudformation.CreateChangeSet,
                            awacs.cloudformation.DeleteChangeSet,
                            awacs.cloudformation.DeleteStack,
                            awacs.cloudformation.CreateStack,
                            awacs.cloudformation.UpdateStack,
                            awacs.cloudformation.SetStackPolicy,
                            awacs.cloudformation.DescribeStacks,
                            awacs.cloudformation.DescribeStackEvents
                        ]
                    )
                ]
            )
        )

        principal = AWSPrincipal(Ref("AWS::AccountId"))
        role = t.add_resource(
            iam.Role(
                "FunctionalTestRole",
                AssumeRolePolicyDocument=Policy(
                    Statement=[
                        Statement(
                            Effect="Allow",
                            Action=[
                                awacs.sts.AssumeRole],
                            Principal=principal)]),
                Policies=[
                    stacker_policy]))

        assumerole_policy = iam.Policy(
            PolicyName="AssumeRole",
            PolicyDocument=Policy(
                Statement=[
                    Statement(
                        Effect="Allow",
                        Resource=[GetAtt(role, "Arn")],
                        Action=[
                            awacs.sts.AssumeRole])]))

        user = t.add_resource(
            iam.User(
                "FunctionalTestUser",
                Policies=[
                    stacker_policy,
                    assumerole_policy]))

        key = t.add_resource(
            iam.AccessKey(
                "FunctionalTestKey",
                Serial=1,
                UserName=Ref(user)))

        t.add_output(Output("User", Value=Ref(user)))
        t.add_output(Output("AccessKeyId", Value=Ref(key)))
        t.add_output(
            Output(
                "SecretAccessKey",
                Value=GetAtt("FunctionalTestKey", "SecretAccessKey")))
        t.add_output(
            Output(
                "FunctionalTestRole",
                Value=GetAtt(role, "Arn")))


class Dummy(Blueprint):
    VARIABLES = {
        "StringVariable": {
            "type": str,
            "default": ""}
    }

    def create_template(self):
        self.template.add_resource(WaitConditionHandle("Dummy"))
        self.template.add_output(Output("DummyId", Value="dummy-1234"))
        self.template.add_output(Output("Region", Value=Ref("AWS::Region")))


class Dummy2(Blueprint):
    """
    This blueprint allows tests of only additional resources to occur.
    Just swap out the Dummy class for Dummy2 on the same stack.
    """
    VARIABLES = {
        "StringVariable": {
            "type": str,
            "default": ""}
    }

    def create_template(self):
        self.template.add_resource(WaitConditionHandle("Dummy"))
        self.template.add_output(Output("DummyId", Value="dummy-1234"))
        self.template.add_resource(WaitConditionHandle("Dummy2"))


class LongRunningDummy(Blueprint):
    """
    Meant to be an attempt to create a cheap blueprint that takes a little bit
    of time to create/rollback/destroy to avoid some of the race conditions
    we've seen in some of our functional tests.
    """
    VARIABLES = {
        "Count": {
            "type": int,
            "description": "The # of WaitConditonHandles to create.",
            "default": 1,
        },
        "BreakLast": {
            "type": bool,
            "description": "Whether or not to break the last WaitConditon "
                           "by creating an invalid WaitConditionHandle.",
            "default": True,
        },
        "OutputValue": {
            "type": str,
            "description": "The value to put in an output to allow for "
                           "updates.",
            "default": "DefaultOutput",
        },
    }

    def create_template(self):
        v = self.get_variables()
        t = self.template
        base_name = "Dummy"

        for i in range(v["Count"]):
            name = "%s%s" % (base_name, i)
            last_name = None
            if i:
                last_name = "%s%s" % (base_name, i - 1)
            wch = WaitConditionHandle(name)
            if last_name is not None:
                wch.DependsOn = last_name
            t.add_resource(wch)

        self.add_output("OutputValue", str(v["OutputValue"]))
        self.add_output("WCHCount", str(v["Count"]))

        if v["BreakLast"]:
            t.add_resource(
                WaitCondition(
                    "BrokenWaitCondition",
                    Handle=wch.Ref(),
                    # Timeout is made deliberately large so CF rejects it
                    Timeout=2 ** 32,
                    Count=0
                )
            )


class Broken(Blueprint):
    """
    This blueprint deliberately fails validation, so that it can be used to
    test re-creation of a failed stack
    """
    VARIABLES = {
        "StringVariable": {
            "type": str,
            "default": ""}
    }

    def create_template(self):
        t = self.template
        t.add_resource(WaitConditionHandle("BrokenDummy"))
        t.add_resource(WaitCondition(
            "BrokenWaitCondition",
            Handle=Ref("BrokenDummy"),
            # Timeout is made deliberately large so CF rejects it
            Timeout=2 ** 32,
            Count=0))
        t.add_output(Output("DummyId", Value="dummy-1234"))


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
        self.template.add_resource(WaitConditionHandle("VPC"))


class DiffTester(Blueprint):
    VARIABLES = {
        "InstanceType": {
            "type": CFNString,
            "description": "NAT EC2 instance type.",
            "default": "m3.medium"},
        "WaitConditionCount": {
            "type": int,
            "description": "Number of WaitConditionHandle resources "
                           "to add to the template"}
    }

    def create_template(self):
        for i in range(self.get_variables()["WaitConditionCount"]):
            self.template.add_resource(WaitConditionHandle("VPC%d" % i))


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


class PreOneOhBastion(Blueprint):
    """Used to ensure old blueprints won't be usable in 1.0"""
    PARAMETERS = {
        "VpcId": {"type": "AWS::EC2::VPC::Id", "description": "Vpc Id"},
        "DefaultSG": {"type": "AWS::EC2::SecurityGroup::Id",
                      "description": "Top level security group."},
        "PublicSubnets": {"type": "List<AWS::EC2::Subnet::Id>",
                          "description": "Subnets to deploy public "
                                         "instances in."},
        "PrivateSubnets": {"type": "List<AWS::EC2::Subnet::Id>",
                           "description": "Subnets to deploy private "
                                          "instances in."},
        "AvailabilityZones": {"type": "CommaDelimitedList",
                              "description": "Availability Zones to deploy "
                                             "instances in."},
        "InstanceType": {"type": "String",
                         "description": "EC2 Instance Type",
                         "default": "m3.medium"},
        "MinSize": {"type": "Number",
                    "description": "Minimum # of instances.",
                    "default": "1"},
        "MaxSize": {"type": "Number",
                    "description": "Maximum # of instances.",
                    "default": "5"},
        "SshKeyName": {"type": "AWS::EC2::KeyPair::KeyName"},
        "OfficeNetwork": {
            "type": "String",
            "description": "CIDR block allowed to connect to bastion hosts."},
        "ImageName": {
            "type": "String",
            "description": "The image name to use from the AMIMap (usually "
                           "found in the config file.)",
            "default": "bastion"},
    }

    def create_template(self):
        return
