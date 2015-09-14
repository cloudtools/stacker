from string import Template
from StringIO import StringIO

import yaml

from .. import exceptions

# register translators (yaml constructors)
from .translators import *  # NOQA


def parse_config(raw_config, environment=None):
    """Parse a config, using it as a template with the environment.

    Args:
        raw_config (str): the raw stacker configuration string.
        environment (Optional[dict]): any environment values that should be
            passed to the config

    Returns:
        dict: the stacker configuration populated with any values passed from
            the environment

    """
    t = Template(raw_config)
    buff = StringIO()
    if not environment:
        environment = {}
    try:
        buff.write(t.substitute(environment))
    except KeyError, e:
        raise exceptions.MissingEnvironment(e.args[0])

    buff.seek(0)
    config = yaml.load(buff)
    return config
