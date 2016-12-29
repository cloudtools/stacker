import unittest

from troposphere import s3

from stacker.blueprints.info import format_var_type
from stacker.blueprints.variables.types import (
    CFNString,
    EC2VPCIdList,
    TroposphereType,
)


class Test(unittest.TestCase):

    def test_format_var_type_troposphere_single_type(self):
        var_type = TroposphereType(s3.Bucket)
        formatted = format_var_type(var_type)
        self.assertEqual(formatted, "troposphere.s3.Bucket")

    def test_format_var_type_troposphere_list_type(self):
        var_type = TroposphereType(s3.Bucket, many=True)
        formatted = format_var_type(var_type)
        self.assertEqual(formatted, "[troposphere.s3.Bucket]")

    def test_format_var_type_troposphere_class(self):
        formatted = format_var_type(s3.LoggingConfiguration)
        self.assertEqual(formatted, "troposphere.s3.LoggingConfiguration")
        formatted = format_var_type([s3.LifecycleConfiguration])
        self.assertEqual(formatted, "[troposphere.s3.LifecycleConfiguration]")

    def test_format_var_type_cfn_type(self):
        formatted = format_var_type(CFNString)
        self.assertEqual(formatted, "CFN::String")
        formatted = format_var_type(EC2VPCIdList)
        self.assertEqual(formatted, "CFN::List<AWS::EC2::VPC::Id>")
