from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


def parse_environment(raw_environment):
    environment = {}
    for line in raw_environment.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('#'):
            continue

        try:
            key, value = line.split(':', 1)
        except ValueError:
            raise ValueError('Environment must be in key: value format')

        environment[key] = value.strip()
    return environment
