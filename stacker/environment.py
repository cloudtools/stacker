
import yaml


class DictWithSourceType(dict):
    """An environment dict which keeps track of its source.

    Environment files may be loaded from simple key/value files, or from
    structured YAML files, and we need to render them using a different
    strategy based on their source. This class adds a source_type property
    to a dict which keeps track of whether the source for the dict is
    yaml or simple.
    """
    def __init__(self, source_type, *args):
        dict.__init__(self, args)
        if source_type not in ['yaml', 'simple']:
            raise ValueError('source_type must be yaml or simple')
        self.source_type = source_type


def parse_environment(raw_environment):
    environment = DictWithSourceType('simple')
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


def parse_yaml_environment(raw_environment):
    environment = DictWithSourceType('yaml')
    parsed_env = yaml.safe_load(raw_environment)

    if not isinstance(parsed_env, dict):
        raise ValueError('Environment must be valid YAML')
    environment.update(parsed_env)
    return environment
