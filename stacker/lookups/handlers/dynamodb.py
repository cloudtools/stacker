from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str
from botocore.exceptions import ClientError
import re
from stacker.session_cache import get_session

from . import LookupHandler
from ...util import read_value_from_path

TYPE_NAME = 'dynamodb'


class DynamodbLookup(LookupHandler):
    @classmethod
    def handle(cls, value, **kwargs):
        """Get a value from a dynamodb table

        dynamodb field types should be in the following format:

            [<region>:]<tablename>@<primarypartionkey>:<keyvalue>.<keyvalue>...

        Note: The region is optional, and defaults to the environment's
        `AWS_DEFAULT_REGION` if not specified.
        """
        value = read_value_from_path(value)
        table_info = None
        table_keys = None
        region = None
        table_name = None
        if '@' in value:
            table_info, table_keys = value.split('@', 1)
            if ':' in table_info:
                region, table_name = table_info.split(':', 1)
            else:
                table_name = table_info
        else:
            raise ValueError('Please make sure to include a tablename')

        if not table_name:
            raise ValueError('Please make sure to include a dynamodb table '
                             'name')

        table_lookup, table_keys = table_keys.split(':', 1)

        table_keys = table_keys.split('.')

        key_dict = _lookup_key_parse(table_keys)
        new_keys = key_dict['new_keys']
        clean_table_keys = key_dict['clean_table_keys']

        projection_expression = _build_projection_expression(clean_table_keys)

        # lookup the data from dynamodb
        dynamodb = get_session(region).client('dynamodb')
        try:
            response = dynamodb.get_item(
                TableName=table_name,
                Key={
                    table_lookup: new_keys[0]
                },
                ProjectionExpression=projection_expression
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise ValueError(
                    'Cannot find the dynamodb table: {}'.format(table_name))
            elif e.response['Error']['Code'] == 'ValidationException':
                raise ValueError(
                    'No dynamodb record matched the partition key: '
                    '{}'.format(table_lookup))
            else:
                raise ValueError('The dynamodb lookup {} had an error: '
                                 '{}'.format(value, e))
        # find and return the key from the dynamo data returned
        if 'Item' in response:
            return (_get_val_from_ddb_data(response['Item'], new_keys[1:]))
        else:
            raise ValueError(
                'The dynamodb record could not be found using the following '
                'key: {}'.format(new_keys[0]))


def _lookup_key_parse(table_keys):
    """Return the order in which the stacks should be executed.

    Args:
        dependencies (dict): a dictionary where each key should be the
            fully qualified name of a stack whose value is an array of
            fully qualified stack names that the stack depends on. This is
            used to generate the order in which the stacks should be
            executed.

    Returns:
        dict: includes a dict of lookup types with data types ('new_keys')
              and a list of the lookups with without ('clean_table_keys')

    """
    # we need to parse the key lookup passed in
    regex_matcher = '\[([^\]]+)]'
    valid_dynamodb_datatypes = ['M', 'S', 'N', 'L']
    clean_table_keys = []
    new_keys = []

    for key in table_keys:
        match = re.search(regex_matcher, key)
        if match:
            # the datatypes are pulled from the dynamodb docs
            if match.group(1) in valid_dynamodb_datatypes:
                match_val = str(match.group(1))
                key = key.replace(match.group(0), '')
                new_keys.append({match_val: key})
                clean_table_keys.append(key)
            else:
                raise ValueError(
                    ('Stacker does not support looking up the datatype: {}')
                    .format(str(match.group(1))))
        else:
            new_keys.append({'S': key})
            clean_table_keys.append(key)
    key_dict = {}
    key_dict['new_keys'] = new_keys
    key_dict['clean_table_keys'] = clean_table_keys

    return key_dict


def _build_projection_expression(clean_table_keys):
    """Given cleaned up keys, this will return a projection expression for
    the dynamodb lookup.

    Args:
        clean_table_keys (dict): keys without the data types attached

    Returns:
        str: A projection expression for the dynamodb lookup.
    """
    projection_expression = ''
    for key in clean_table_keys[:-1]:
        projection_expression += ('{},').format(key)
    projection_expression += clean_table_keys[-1]
    return projection_expression


def _get_val_from_ddb_data(data, keylist):
    """Given a dictionary of dynamodb data (including the datatypes) and a
    properly structured keylist, it will return the value of the lookup

    Args:
        data (dict): the raw dynamodb data
            keylist(list): a list of keys to lookup. This must include the
                datatype

    Returns:
        various: It returns the value from the dynamodb record, and casts it
            to a matching python datatype
    """
    next_type = None
    # iterate through the keylist to find the matching key/datatype
    for k in keylist:
        for k1 in k:
            if next_type is None:
                data = data[k[k1]]
            else:
                temp_dict = data[next_type]
                data = temp_dict[k[k1]]
            next_type = k1
    if next_type == 'L':
        # if type is list, convert it to a list and return
        return _convert_ddb_list_to_list(data[next_type])
    if next_type == 'N':
        # TODO: handle various types of 'number' datatypes, (e.g. int, double)
        # if a number, convert to an int and return
        return int(data[next_type])
    # else, just assume its a string and return
    return str(data[next_type])


def _convert_ddb_list_to_list(conversion_list):
    """Given a dynamodb list, it will return a python list without the dynamodb
        datatypes

    Args:
        conversion_list (dict): a dynamodb list which includes the
            datatypes

    Returns:
        list: Returns a sanitized list without the dynamodb datatypes
    """
    ret_list = []
    for v in conversion_list:
        for v1 in v:
            ret_list.append(v[v1])
    return ret_list
