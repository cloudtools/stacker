from mock import MagicMock

from stacker.context import Context
from stacker.lookups import Lookup


def mock_provider(**kwargs):
    return MagicMock(**kwargs)


def mock_context(namespace=None, **kwargs):
    environment = kwargs.get("environment", {})
    if namespace is not None:
        environment["namespace"] = namespace

    return Context(environment, **kwargs)


def generate_definition(base_name, stack_id, **overrides):
    definition = {
        "name": "%s.%d" % (base_name, stack_id),
        "class_path": "stacker.tests.fixtures.mock_blueprints.%s" % (
            base_name.upper()),
        "namespace": "example-com",
        "parameters": {
            "InstanceType": "m3.medium",
            "AZCount": 2,
        },
        "requires": []
    }
    definition.update(overrides)
    return definition


def mock_lookup(lookup_input, lookup_type='output', raw=None):
    if raw is None:
        raw = lookup_input
    return Lookup(type=lookup_type, input=lookup_input, raw=raw)
