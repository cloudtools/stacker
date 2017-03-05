TYPE_NAME = "default"


def handler(value, **kwargs):
    """Use a value from the environment or fall back to a default if the
       environment doesn't contain the variable.

    Format of value:

        <env_var>::<default value>

    For example:

        Groups: ${default app_security_groups::sg-12345,sg-67890}

    If `app_security_groups` is defined in the environment, its defined value
    will be returned. Otherwise, `sg-12345,sg-67890` will be the returned
    value.

    This allows defaults to be set at the config file level.
    """

    try:
        env_var_name, default_val = value.split("::", 1)
    except ValueError:
        raise ValueError("Invalid value for default: %s. Must be in "
                         "<env_var>::<default value> format." % value)

    if env_var_name in kwargs['context'].environment:
        return kwargs['context'].environment[env_var_name]
    else:
        return default_val
