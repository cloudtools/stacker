from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from past.builtins import basestring
from builtins import object
from string import Template

from .exceptions import InvalidLookupCombination
from .lookups import (
    extract_lookups,
    resolve_lookups,
)


class LookupTemplate(Template):

    """A custom string template we use to replace lookup values"""
    idpattern = r'[_a-z][^\$\{\}]*'


def resolve_string(value, replacements):
    """Resolve any lookups within a string.

    Args:
        value (str): string value we're resolving lookups within
        replacements (dict): resolved lookup values

    Returns:
        str: value with any lookups resolved

    """
    lookups = extract_lookups(value)
    for lookup in lookups:
        lookup_value = replacements.get(lookup.raw)
        if not isinstance(lookup_value, basestring):
            if len(lookups) > 1:
                raise InvalidLookupCombination(lookup, lookups, value)
            return lookup_value
    # we use safe_substitute to support resolving nested lookups
    return LookupTemplate(value).safe_substitute(replacements)


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
        for key, v in value.items():
            value[key] = resolve(v, replacements)
        return value
    return value


def resolve_variables(variables, context, provider):
    """Given a list of variables, resolve all of them.

    Args:
        variables (list of :class:`stacker.variables.Variable`): list of
            variables
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
    def needs_resolution(self):
        """Return True if the value has any lookups that need resolving."""
        if self.lookups:
            return True
        return False

    @property
    def value(self):
        """Return the current value of the Variable.

        `_resolved_value` takes precedence over `_value`.

        """
        if self._resolved_value is not None:
            return self._resolved_value
        else:
            return self._value

    @property
    def resolved(self):
        """Boolean for whether the Variable has been resolved.

        Variables only need to be resolved if they contain lookups.

        """
        if self.needs_resolution:
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
            resolved_lookups = resolve_lookups(self, context, provider)
            self.replace(resolved_lookups)

    def replace(self, resolved_lookups):
        """Replace lookups in the Variable with their resolved values.

        Args:
            resolved_lookups (dict): dict of :class:`stacker.lookups.Lookup` ->
                resolved value.

        """
        replacements = {}
        for lookup, value in resolved_lookups.items():
            replacements[lookup.raw] = value

        self._resolved_value = resolve(self.value, replacements)
