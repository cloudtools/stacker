from stacker.session_cache import get_session
import re, operator

from ...util import read_value_from_path

TYPE_NAME = "ami"

import sys
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

    ec2 = get_session(None).client('ec2')

    values = {}
    describe_args = {}

    # now find any other arguments that can be filters
    matches = re.findall('([0-9a-zA-z_-]+:[^\s$]+)', value)
    for match in matches:
        key, value = match.split(':', 1)
        values[key] = value

    if not values.get('owners'):
        raise Exception("'owners' value required when using ami")
    owners = values.pop('owners').split(',')
    describe_args["Owners"] = owners

    ### TODO do the regex
    if not values.get('name_regex'):
        raise Exception("'name_regex' value required when using ami")
    name_regex = values.pop('name_regex')

    executable_users = None
    if values.get('executable_users'):
        executable_users = values.pop('executable_users').split(',')
        describe_args["ExecutableUsers"] = executable_users

    filters = []
    for name, value in values.iteritems():
        filters.append({"Name":name, "Values":value.split(',')})
    describe_args["Filters"] = filters

    result = ec2.describe_images(**describe_args)

    images = sorted(result['Images'], key=operator.itemgetter('CreationDate'), reverse=True)
    for image in images:
        if re.match("^%s$" % name_regex, image['Name']):
            return image['ImageId']

    raise Exception("Failed to find ami")
