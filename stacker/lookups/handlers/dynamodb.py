from botocore.exceptions import ClientError
import re
from stacker.session_cache import get_session

from ...util import read_value_from_path

TYPE_NAME = "dynamodb"


def handler(value, **kwargs):
    """Get a value from a dynamodb table

    dynamodb field types should be in the following format:

        [<region>:<tablename>@]<primarypartionkey>.<keyvalue>.<keyvalue>...

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

    clean_table_keys, new_keys = []
    regex_matcher = "\[([^\]]+)]"

    #we need to parse the key lookup passed in
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
                    'Stacker does not support looking up that datatype')
        else:
            new_keys.append({"S": key})
            clean_table_keys.append(key)

    projection_expression = _buildProjectionExpression(clean_table_keys)

    #lookup the data from dynamodb
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

    #find and return the key from the dynamo data returned
    if 'Item' in response:
        if len(response['Item']) > 0:
            return (_getValFromDict(response['Item'], new_keys[1:]))
        else:
            raise ValueError('The specified dynamo record could not be found')
    else:
        raise ValueError(
            'No dynamo record with those paramters could be found')


def _buildProjectionExpression(clean_table_keys):
    """this builds the lookup for dynamodb
    """
    projection_expression = ""
    for key in clean_table_keys[:-1]:
        projection_expression += ("{},").format(key)
    projection_expression += clean_table_keys[-1]
    return projection_expression


def _getValFromDict(data, keylist):
    """This finds the key inside the data returned by dynamodb
    """
    nextType = None
    for k in keylist:
        for k1 in k:
            if nextType is None:
                data = data[k[k1]]
            else:
                temp_dict = data[nextType]
                data = temp_dict[k[k1]]
            nextType = k1
    if nextType == "L":
        return _convertDDBListToList(data[nextType]
    if nextType == "N":
        return int(data[nextType])
    return str(data[nextType])

def _convertDDBListToList(convlist):
    """This removes the variable types from the list before passing it to the
        lookup
    """
    ret_list = []
    for v in convlist:
        for v1 in v:
            ret_list.append(v[v1])
    return ret_list
