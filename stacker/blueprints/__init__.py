from troposphere import Output, Ref
from troposphere import s3

from stacker.blueprints.base import Blueprint


class StackerBucket(Blueprint):
    VARIABLES = {
        "BucketName": {
            "type": str,
            "default": "",
            "description": "When provided, specifies an explicit bucket name "
                           "to use when creating the bucket. If none is "
                           "specified, CloudFormation will create a random "
                           "name."
        }
    }

    @property
    def bucket(self):
        bucket_name = self.get_variables()["BucketName"] or Ref("AWS::NoValue")
        return s3.Bucket("StackerBucket", BucketName=bucket_name)

    def create_template(self):
        self.template.add_resource(self.bucket)
        self.template.add_output(Output("BucketId", Value=self.bucket.Ref()))
