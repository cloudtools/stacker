from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
TYPE_NAME = "split"


def handler(value, **kwargs):
    """Split the supplied string on the given delimiter, providing a list.

    Format of value:

        <delimiter>::<value>

    For example:

        Subnets: ${split ,::subnet-1,subnet-2,subnet-3}

    Would result in the variable `Subnets` getting a list consisting of:

        ["subnet-1", "subnet-2", "subnet-3"]

    This is particularly useful when getting an output from another stack that
    contains a list. For example, the standard vpc blueprint outputs the list
    of Subnets it creates as a pair of Outputs (PublicSubnets, PrivateSubnets)
    that are comma separated, so you could use this in your config:

        Subnets: ${split ,::${output vpc::PrivateSubnets}}
    """

    try:
        delimiter, text = value.split("::", 1)
    except ValueError:
        raise ValueError("Invalid value for split: %s. Must be in "
                         "<delimiter>::<text> format." % value)

    return text.split(delimiter)
