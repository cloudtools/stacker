import subprocess


def get_vaulted_value(value):
    """Get the specified value from vault.

    Vaulted field types should use the following format:

        <path within vault>@<key within stored vault data>

    For example:

        # We've set the secret/hello key with the following
        $ vault write secret/hello value=world

        # In stacker we would reference "world" with the following
        conf_key: !vault secret/hello@value

        # The above would resolve to
        conf_key: world

    """
    try:
        path, key = value.split('@', 1)
    except ValueError:
        raise TypeError(
            'Vaulted vaules must be of the format'
            ' "<path in vault>@<key in stored data>" (got %s)' % (value,)
        )

    return subprocess.check_output(
        ['vault', 'read', '-field=%s' % (key,), path]).strip()


def vault_constructor(loader, node):
    value = loader.construct_scalar(node)
    return get_vaulted_value(value)
