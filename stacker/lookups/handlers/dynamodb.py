from botocore.exceptions import ClientError
import re
from stacker.session_cache import get_session

from ...util import read_value_from_path

TYPE_NAME = "dynamodb"


def handler(value, **kwargs):
    """Get a value from a dynamodb table

    dynamodb field types should be in the following format:

        [<region>:]<tablename>@<primarypartionkey>.<keyvalue>.<keyvalue>...

    Note: The region is optional, and defaults to the environment's
    `AWS_DEFAULT_REGION` if not specified.
    """
    value = read_value_from_path(value)
    table_info = None
    table_keys = None
    region = None
    table_name = None

    if "@" in value:
        table_info, table_keys = value.split("@", 1)
        if ":" in table_info:
            region, table_name = table_info.split(":", 1)
        else:
            table_name = table_info
    else:
        raise ValueError('Please make sure to include a tablename')

    if table_name is None:
        raise ValueError('Please make sure to include a dynamodb table name')

    table_lookup, table_keys = table_keys.split(":", 1)
    table_keys = table_keys.split(".")

    clean_table_keys = []
    new_keys = []
    regex_matcher = "\[([^\]]+)]"

    # we need to parse the key lookup passed in
    for key in table_keys:
        match = re.search(regex_matcher, key)
        if match:
            if match.group(1) in ["M", "S", "N", "L"]:
                match_val = str(match.group(1))
                key = key.replace(match.group(0), "")
                new_keys.append({match_val: key})
                clean_table_keys.append(key)
            else:
                raise ValueError(
                    'Stacker does not support looking up the datatype: {}').format(str(match.group(1)))
        else:
            new_keys.append({"S": key})
            clean_table_keys.append(key)

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
            raise ValueError('Cannot find the dynamodb table: ' + table_name)
        elif e.response['Error']['Code'] == 'ValidationException':
            raise ValueError('No dynamo record matched that partition key')

    # find and return the key from the dynamo data returned
    if 'Item' in response:
        if len(response['Item']) > 0:
            return (_get_val_from_ddb_data(response['Item'], new_keys[1:]))
        else:
            raise ValueError('The specified dynamo record could not be found')
    else:
        raise ValueError(
            'No dynamo record with those parameters could be found')


def _build_projection_expression(clean_table_keys):
        """Given cleaned up keys, this will return a projection expression for
        the dynamodb lookup.

        Args:
            clean_table_keys (dictionary)  : keys without the data types attached

        Returns:
            string: A projection expression for the dynamodb lookup.
        """
    projection_expression = ""
    for key in clean_table_keys[:-1]:
        projection_expression += ("{},").format(key)
    projection_expression += clean_table_keys[-1]
    return projection_expression


def _get_val_from_ddb_data(data, keylist):
    """Given a dictionary of dynamodb data (including the datatypes) and a
    properly structured keylist, it will return the value of the lookup

    Args:
        - data(dictionary): the raw dynamodb data
            keylist(list): a list of keys to lookup. This must include the data type

    Returns:
        various: It returns the value from the dynamodb record, and casts it
            to a matching python datatype
    """
    nextType = None
    #iterate through the keylist to find the matching key/datatype
    for k in keylist:
        for k1 in k:
            if nextType is None:
                data = data[k[k1]]
            else:
                temp_dict = data[nextType]
                data = temp_dict[k[k1]]
            nextType = k1
    if nextType == "L":
        #if type is list, convert it to a list and return
        return _convert_ddb_list_to_list(data[nextType])
    if nextType == "N":
        # TODO: handle various types of 'number' datatypes, (e.g. int, double)
        #if a number, convert to an int and return
        return int(data[nextType])
    #else, just assume its a string and return
    return str(data[nextType])


def _convert_ddb_list_to_list(convlist):
    """This removes the variable types from the list before passing it to the
        lookup
    """
    ret_list = []
    for v in convlist:
        for v1 in v:
            ret_list.append(v[v1])
    return ret_list
