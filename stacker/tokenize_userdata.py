import re

from troposphere import Ref, GetAtt


HELPERS = {
    'Ref': Ref,
    'Fn::GetAtt': GetAtt
}

split_string = "(" + "|".join([r"%s\([^)]+\)" % h for h in HELPERS]) + ")"
replace_string = \
    r"(?P<helper>%s)\((?P<args>['\"]?[^)]+['\"]?)+\)" % '|'.join(HELPERS)

split_re = re.compile(split_string)
replace_re = re.compile(replace_string)


def cf_tokenize(s):
    """ Parses UserData for Cloudformation helper functions.

    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html
    http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference.html
    http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/quickref-cloudformation.html#scenario-userdata-base64

    It breaks apart the given string at each recognized function (see HELPERS)
    and instantiates the helper function objects in place of those.

    Returns a list of parts as a result. Useful when used with Join() and
    Base64() CloudFormation functions to produce user data.

    ie: Base64(Join('', cf_tokenize(userdata_string)))
    """
    t = []
    parts = split_re.split(s)
    for part in parts:
        cf_func = replace_re.search(part)
        if cf_func:
            args = [a.strip("'\" ") for a in cf_func.group('args').split(',')]
            t.append(HELPERS[cf_func.group('helper')](*args).data)
        else:
            t.append(part)
    return t
