from stacker.blueprints.base import Blueprint

from troposphere import Ref
from troposphere import s3


class StackerBucket(Blueprint):
    VARIABLES = {
        "BucketName": {
            "type": str,
            "default": "",
            "description": "When provided, specifies an explicit bucket name "
                           "to use when creating the bucket. If none is "
                           "specified, CloudFormation will create a random "
                           "name."
        },
    }

    @property
    def bucket(self):
        bucket_name = self.get_variables()["BucketName"] or Ref("AWS::NoValue")
        aes = s3.ServerSideEncryptionRule(
                ServerSideEncryptionByDefault=s3.ServerSideEncryptionByDefault(
                    SSEAlgorithm="AES256"))

        return s3.Bucket(
            "StackerBucket",
            BucketName=bucket_name,
            BucketEncryption=s3.BucketEncryption(
                ServerSideEncryptionConfiguration=[aes]))

    def create_template(self):
        self.template.add_resource(self.bucket)
