from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import re

from past.builtins import basestring
from builtins import object
from string import Template

from .exceptions import InvalidLookupCombination, UnresolvedVariable, \
    UnknownLookupType, FailedVariableLookup, FailedLookup, \
    UnresolvedVariableValue, InvalidLookupConcatenation
from .lookups.registry import LOOKUP_HANDLERS


class LookupTemplate(Template):

    """A custom string template we use to replace lookup values"""
    idpattern = r'[_a-z][^\$\{\}]*'


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
        value (any): Initial value of the variable from the config (str, list,
                     dict)
    """

    def __init__(self, name, value):
        self.name = name
        self._raw_value = value
        self._value = VariableValue.parse(value)

    @property
    def value(self):
        """Return the current value of the Variable.
        """
        try:
            return self._value.value()
        except UnresolvedVariableValue:
            raise UnresolvedVariable("<unknown>", self)
        except InvalidLookupConcatenation as e:
            raise InvalidLookupCombination(e.lookup, e.lookups, self)

    @property
    def resolved(self):
        """Boolean for whether the Variable has been resolved.

        Variables only need to be resolved if they contain lookups.
        """
        return self._value.resolved()

    def resolve(self, context, provider):
        """Recursively resolve any lookups with the Variable.

        Args:
            context (:class:`stacker.context.Context`): Current context for
                building the stack
            provider (:class:`stacker.provider.base.BaseProvider`): subclass of
                the base provider

        """
        try:
            self._value.resolve(context, provider)
        except FailedLookup as e:
            raise FailedVariableLookup(self.name, e.lookup, e.error)

    def dependencies(self):
        """
        Returns:
            Set[str]: Stack names that this variable depends on
        """
        return self._value.dependencies()


class VariableValue(object):
    """
    Abstract Syntax Tree base object to parse the value for a variable
    """
    def value(self):
        return NotImplementedError()

    def __iter__(self):
        return NotImplementedError()

    def resolved(self):
        """
        Returns:
            bool: Whether value() will not raise an error
        """
        return NotImplementedError()

    def resolve(self, context, provider):
        pass

    def dependencies(self):
        return set()

    def simplified(self):
        """
        Return a simplified version of the Value.
        This can be used to e.g. concatenate two literals in to one literal, or
        to flatten nested Concatenations

        Returns:
            VariableValue
        """
        return self

    @classmethod
    def parse(cls, input_object):
        if isinstance(input_object, list):
            return VariableValueList.parse(input_object)
        elif isinstance(input_object, dict):
            return VariableValueDict.parse(input_object)
        elif not isinstance(input_object, basestring):
            return VariableValueLiteral(input_object)
        # else:  # str

        tokens = VariableValueConcatenation([
            VariableValueLiteral(t)
            for t in re.split(r'(\$\{|\}|\s+)', input_object)
        ])

        opener = '${'
        closer = '}'

        while True:
            last_open = None
            next_close = None
            for i, t in enumerate(tokens):
                if not isinstance(t, VariableValueLiteral):
                    continue

                if t.value() == opener:
                    last_open = i
                    next_close = None
                if last_open is not None and \
                        t.value() == closer and \
                        next_close is None:
                    next_close = i

            if next_close is not None:
                lookup_data = VariableValueConcatenation(
                    tokens[(last_open + len(opener) + 1):next_close]
                )
                lookup = VariableValueLookup(
                    lookup_name=tokens[last_open + 1],
                    lookup_data=lookup_data,
                )
                tokens[last_open:(next_close + 1)] = [lookup]
            else:
                break

        tokens = tokens.simplified()

        return tokens


class VariableValueLiteral(VariableValue):
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def __iter__(self):
        yield self

    def resolved(self):
        return True

    def __repr__(self):
        return "Literal<{}>".format(repr(self._value))


class VariableValueList(VariableValue, list):
    @classmethod
    def parse(cls, input_object):
        acc = [
            VariableValue.parse(obj)
            for obj in input_object
        ]
        return cls(acc)

    def value(self):
        return [
            item.value()
            for item in self
        ]

    def resolved(self):
        accumulator = True
        for item in self:
            accumulator = accumulator and item.resolved()
        return accumulator

    def __repr__(self):
        return "List[{}]".format(', '.join([repr(value) for value in self]))

    def __iter__(self):
        return list.__iter__(self)

    def resolve(self, context, provider):
        for item in self:
            item.resolve(context, provider)

    def dependencies(self):
        deps = set()
        for item in self:
            deps.update(item.dependencies())
        return deps

    def simplified(self):
        return [
            item.simplified()
            for item in self
        ]


class VariableValueDict(VariableValue, dict):
    @classmethod
    def parse(cls, input_object):
        acc = {
            k: VariableValue.parse(v)
            for k, v in input_object.items()
        }
        return cls(acc)

    def value(self):
        return {
            k: v.value()
            for k, v in self.items()
        }

    def resolved(self):
        accumulator = True
        for item in self.values():
            accumulator = accumulator and item.resolved()
        return accumulator

    def __repr__(self):
        return "Dict[{}]".format(', '.join([
            "{}={}".format(k, repr(v)) for k, v in self.items()
        ]))

    def __iter__(self):
        return dict.__iter__(self)

    def resolve(self, context, provider):
        for item in self.values():
            item.resolve(context, provider)

    def dependencies(self):
        deps = set()
        for item in self.values():
            deps.update(item.dependencies())
        return deps

    def simplified(self):
        return {
            k: v.simplified()
            for k, v in self.items()
        }


class VariableValueConcatenation(VariableValue, list):
    def value(self):
        if len(self) == 1:
            return self[0].value()

        values = []
        for value in self:
            resolved_value = value.value()
            if not isinstance(resolved_value, basestring):
                raise InvalidLookupConcatenation(value, self)
            values.append(resolved_value)
        return ''.join(values)

    def __iter__(self):
        return list.__iter__(self)

    def resolved(self):
        accumulator = True
        for item in self:
            accumulator = accumulator and item.resolved()
        return accumulator

    def __repr__(self):
        return "Concat[{}]".format(', '.join([repr(value) for value in self]))

    def resolve(self, context, provider):
        for value in self:
            value.resolve(context, provider)

    def dependencies(self):
        deps = set()
        for item in self:
            deps.update(item.dependencies())
        return deps

    def simplified(self):
        concat = []
        for item in self:
            if isinstance(item, VariableValueLiteral) and \
                    item.value() == '':
                pass

            elif isinstance(item, VariableValueLiteral) and \
                    len(concat) > 0 and \
                    isinstance(concat[-1], VariableValueLiteral):
                # Join the literals together
                concat[-1] = VariableValueLiteral(
                    concat[-1].value() + item.value()
                )

            elif isinstance(item, VariableValueConcatenation):
                # Flatten concatenations
                concat.extend(item.simplified())

            else:
                concat.append(item.simplified())

        if len(concat) == 0:
            return VariableValueLiteral('')
        elif len(concat) == 1:
            return concat[0]
        else:
            return VariableValueConcatenation(concat)


class VariableValueLookup(VariableValue):
    def __init__(self, lookup_name, lookup_data, handler=None):
        """
        Args:
            lookup_name (basestring): Name of the invoked lookup
            lookup_data (VariableValue): Data portion of the lookup
        """
        self._resolved = False
        self._value = None

        self.lookup_name = lookup_name

        if isinstance(lookup_data, basestring):
            lookup_data = VariableValueLiteral(lookup_data)
        self.lookup_data = lookup_data

        if handler is None:
            lookup_name_resolved = lookup_name.value()
            try:
                handler = LOOKUP_HANDLERS[lookup_name_resolved]
            except KeyError:
                raise UnknownLookupType(lookup_name_resolved)
        self.handler = handler

    def resolve(self, context, provider):
        self.lookup_data.resolve(context, provider)
        try:
            if type(self.handler) == type:
                # Hander is a new-style handler
                result = self.handler.handle(
                    value=self.lookup_data.value(),
                    context=context,
                    provider=provider
                )
            else:
                result = self.handler(
                    value=self.lookup_data.value(),
                    context=context,
                    provider=provider
                )
            self._resolve(result)
        except Exception as e:
            raise FailedLookup(self, e)

    def _resolve(self, value):
        self._value = value
        self._resolved = True

    def dependencies(self):
        if type(self.handler) == type:
            return self.handler.dependencies(self.lookup_data)
        else:
            return set()

    def value(self):
        if self._resolved:
            return self._value
        else:
            raise UnresolvedVariableValue(self)

    def __iter__(self):
        yield self

    def resolved(self):
        return self._resolved

    def __repr__(self):
        if self._resolved:
            return "Lookup<{r} ({t} {d})>".format(
                r=self._value,
                t=self.lookup_name,
                d=repr(self.lookup_data),
            )
        else:
            return "Lookup<{t} {d}>".format(
                t=self.lookup_name,
                d=repr(self.lookup_data),
            )

    def __str__(self):
        return "${{{type} {data}}}".format(
            type=self.lookup_name.value(),
            data=self.lookup_data.value(),
        )

    def simplified(self):
        return VariableValueLookup(
            lookup_name=self.lookup_name,
            lookup_data=self.lookup_data.simplified(),
        )
