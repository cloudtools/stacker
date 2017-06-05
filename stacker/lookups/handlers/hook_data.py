TYPE_NAME = "hook_data"


def handler(value, context, **kwargs):
    """Returns the value of a key for a given hook in hook_data.

    Format of value:

        <hook_name>::<key>
    """
    try:
        hook_name, key = value.split("::")
    except ValueError:
        raise ValueError("Invalid value for hook_data: %s. Must be in "
                         "<hook_name>::<key> format." % value)

    return context.hook_data[hook_name][key]
