from stacker.session_cache import get_session

from ...util import read_value_from_path

TYPE_NAME = "ami"


def handler(value, **kwargs):
    """Fetch the most recent AMI Id using a filter

    For example:

        ${ami: owners:self,account,amazon
            name_regex:serverX-[0-9]+
            architecture:x64,i386
            }

        The above fetches the most recent AMI where owner is self
        account or amazon and the ami name matches the regex described,
        the architecture will be either x64 or i386

        Valid arguments:

        owners (comma delimited) REQUIRED ONCE:
            aws_account_id | amazon | self

        name_regex (a regex) REQUIRED ONCE:
            e.g. my-ubuntu-server-[0-9]+

        executable_users (comma delimited) OPTIONAL ONCE:
            aws_account_id | amazon | self

        Any other arguments specified are sent as filters to the aws api
        For example, "architecture:x86_64" will add a filter
    """
    value = read_value_from_path(value)

    ec2 = get_session().client('ec2')

    matches = re.match('owners:([A-Z0-9a-z,]+)', value)
    owners = matches.group(1).split(',')

    matches = re.match('executable_users:([A-Z0-9a-z,]+)', value)
    executable_users = matches.group(1).split(',')

    ec2.describe_images(
            Owners=owners,
            ExecutableUsers=executable_users
        )

    decoded = value.decode("base64")
    return kms.decrypt(CiphertextBlob=decoded)["Plaintext"]
