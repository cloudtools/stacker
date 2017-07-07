from stacker.session_cache import get_session
import re
import operator

from ...util import read_value_from_path

TYPE_NAME = "ami"


class ImageNotFound(Exception):
    def __init__(self, search_string):
        self.search_string = search_string
        message = ("Unable to find ec2 image with search string: {}").format(
            search_string
        )
        super(ImageNotFound, self).__init__(message)


def handler(value, provider, **kwargs):
    """Fetch the most recent AMI Id using a filter

    For example:

        ${ami [<region>@]owners:self,account,amazon name_regex:serverX-[0-9]+ architecture:x64,i386}

        The above fetches the most recent AMI where owner is self
        account or amazon and the ami name matches the regex described,
        the architecture will be either x64 or i386

        You can also optionally specify the region in which to perform the AMI lookup.

        Valid arguments:

        owners (comma delimited) REQUIRED ONCE:
            aws_account_id | amazon | self

        name_regex (a regex) REQUIRED ONCE:
            e.g. my-ubuntu-server-[0-9]+

        executable_users (comma delimited) OPTIONAL ONCE:
            aws_account_id | amazon | self

        Any other arguments specified are sent as filters to the aws api
        For example, "architecture:x86_64" will add a filter
    """  # noqa
    value = read_value_from_path(value)

    if "@" in value:
        region, value = value.split("@", 1)
    else:
        region = provider.region

    ec2 = get_session(region).client('ec2')

    values = {}
    describe_args = {}

    # now find any other arguments that can be filters
    matches = re.findall('([0-9a-zA-z_-]+:[^\s$]+)', value)
    for match in matches:
        k, v = match.split(':', 1)
        values[k] = v

    if not values.get('owners'):
        raise Exception("'owners' value required when using ami")
    owners = values.pop('owners').split(',')
    describe_args["Owners"] = owners

    if not values.get('name_regex'):
        raise Exception("'name_regex' value required when using ami")
    name_regex = values.pop('name_regex')

    executable_users = None
    if values.get('executable_users'):
        executable_users = values.pop('executable_users').split(',')
        describe_args["ExecutableUsers"] = executable_users

    filters = []
    for k, v in values.iteritems():
        filters.append({"Name": k, "Values": v.split(',')})
    describe_args["Filters"] = filters

    result = ec2.describe_images(**describe_args)

    images = sorted(result['Images'], key=operator.itemgetter('CreationDate'),
                    reverse=True)
    for image in images:
        if re.match("^%s$" % name_regex, image['Name']):
            return image['ImageId']

    raise ImageNotFound(value)
