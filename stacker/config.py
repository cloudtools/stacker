from string import Template
from StringIO import StringIO

import yaml

from . import exceptions


def parse_config(config_string, environment=None):
    """ Parse a config, using it as a template with the environment. """
    t = Template(config_string)
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
