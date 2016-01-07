import os


def get_config_directory():
    """Return the directory the config file is located in.

    This enables us to use relative paths in config values.

    """
    # avoid circular import
    from ...commands.stacker import Stacker
    command = Stacker()
    namespace = command.parse_args()
    return os.path.dirname(namespace.config.name)


def read_value_from_path(value):
    """Enables translators to read values from files.

    The value can be referred to with the `file://` prefix. ie:

        conf_key: !kms file://kms_value.txt

    """
    if value.startswith('file://'):
        path = value.split('file://', 1)[1]
        config_directory = get_config_directory()
        relative_path = os.path.join(config_directory, path)
        with open(relative_path) as read_file:
            value = read_file.read()
    return value
