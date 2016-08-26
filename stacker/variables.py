from string import Template

from .lookups import (
    extract_lookups,
    resolve_lookups,
)


class OutputTemplate(Template):
    """A custom string template we use to replace lookup values"""
    idpattern = r'[_a-z][_a-z0-9\s\:\-\.\,]*'


def resolve_string(value, replacements):
    """Resolve any output lookups within a string.

    Args:
        value (str): string value we're resolving lookups within
        replacements (dict): resolved output values

    Returns:
        str: value with any lookups resolved

    """
    # we use safe_substitute to support resolving nested lookups
    return OutputTemplate(value).safe_substitute(replacements)


def resolve(value, replacements):
    """Recursively resolve any lookups within the data structure.

    Args:
        value (Union[str, list, dict]): a structure that contains lookups
        replacements: resolved lookup values

    Returns:
        Union[str, list, dict]: value passed in with lookup values resolved

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
    """Given a list of variables, resolve all of them.

    Args:
        variables (list): list of `stacker.variables.Variables`
        context (:class:`stacker.context.Context`): stacker context
        provider (:class:`stacker.provider.base.BaseProvider`): subclass of the
            base provider

    """
    for variable in variables:
        variable.resolve(context, provider)


class Variable(object):
    """Represents a variable passed to a stack.

    Args:
        name (str): Name of the variable
        value (str): Initial value of the variable from the config

    """

    def __init__(self, name, value):
        self.name = name
        self._value = value
        self._resolved_value = None

    @property
    def lookups(self):
        """Return any lookups within the value"""
        return extract_lookups(self.value)

    @property
    def value(self):
        """Return the current value of the Variable.

        `_resolved_value` takes precedence over `_value`.

        """
        return self._resolved_value or self._value

    @property
    def resolved(self):
        """Boolean for whether the Variable has been resolved.

        Variables only need to be resolved if they contain lookups.

        """
        if self.lookups:
            return self._resolved_value is not None
        return True

    def resolve(self, context, provider):
        """Recursively resolve any lookups with the Variable.

        Args:
            context (:class:`stacker.context.Context`): Current context for
                building the stack
            provider (:class:`stacker.provider.base.BaseProvider`): subclass of
                the base provider

        """
        while self.lookups:
            resolved_lookups = resolve_lookups(self.lookups, context, provider)
            self.replace(resolved_lookups)

    def replace(self, resolved_lookups):
        """Replace lookups in the Variable with their resolved values.

        Args:
            resolved_lookups (dict): dict of Lookup -> resolved value.

        """
        replacements = {}
        for lookup, value in resolved_lookups.iteritems():
            replacements[lookup.raw] = value

        self._resolved_value = resolve(self.value, replacements)
