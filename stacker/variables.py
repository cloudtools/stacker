from string import Template

from .lookups import (
    extract_lookups,
    resolve_lookups,
)


class OutputTemplate(Template):
    idpattern = r'[_a-z][_a-z0-9\s\:\-\.\,]*'


def resolve_string(value, replacements):
    """Resolve any output lookups within a string.

    Args:
        value (str): string value we're resolving lookups within
        replacements (dict): resolved output values

    Returns:
        str: value with any lookups resolved

    """
    return OutputTemplate(value).safe_substitute(replacements)


def resolve(value, replacements):
    """Recursively resolve any lookups within the data structure.

    Args:
        value (Union[str, list, dict]): a structure that contains lookups
        replacements: resolved output values

    Returns:
        Union[str, list, dict]: value passed in with output values resolved

    """
    if isinstance(value, basestring):
        return resolve_string(value, replacements)
    elif isinstance(value, list):
        resolved = []
        for v in value:
            resolved.append(resolve(v, replacements))
        return resolved
    elif isinstance(value, dict):
        for key, v in value.iteritems():
            value[key] = resolve(v, replacements)
        return value
    return value


def resolve_variables(variables, context, provider):
    for variable in variables:
        variable.resolve(context, provider)


class Variable(object):

    def __init__(self, name, value):
        self.name = name
        self._value = value
        self._resolved_value = None

    @property
    def lookups(self):
        return extract_lookups(self.value)

    @property
    def value(self):
        return self._resolved_value or self._value

    @property
    def resolved(self):
        if self.lookups:
            return self._resolved_value is not None
        return True

    def resolve(self, context, provider):
        while self.lookups:
            resolved_lookups = resolve_lookups(self.lookups, context, provider)
            self.replace(resolved_lookups)

    def replace(self, resolved_lookups):
        replacements = {}
        for lookup, value in resolved_lookups.iteritems():
            replacements[lookup.raw] = value

        self._resolved_value = resolve(self.value, replacements)
