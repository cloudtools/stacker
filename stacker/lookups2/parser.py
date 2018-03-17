from collections import namedtuple

from .lexer import (
    T_STRING,
    T_WS,
    T_LOOKUP_START,
    T_LOOKUP_END,
)


Tree = namedtuple("Tree", ("values"))
Lookup = namedtuple("Lookup", ("type", "value"))


class Parser(object):
    """This is a simple Recursive Descent parse, which takes a stream of tokens
    from a :class:`stacker.lookups.Lexer` and converts it to a
    :class:`stacker.lookups.parser.Tree`.

    See https://en.wikipedia.org/wiki/Recursive_descent_parser
    """

    def __init__(self, tokens):
        self.tokens = tokens

    def parse(self):
        ast, _ = self._parse(self.tokens)
        return ast

    def _parse(self, tokens):
        return self.parse_value(tokens)

    def parse_value(self, tokens):
        values = []
        while tokens:
            token = tokens[0]
            if token.type == T_LOOKUP_END:
                break
            elif token.type == T_LOOKUP_START:
                value, tokens = self.parse_lookup(tokens)
            elif token.type == T_STRING:
                value, tokens = self.parse_string(tokens)
            elif token.type == T_WS:
                value, tokens = self.parse_ws(tokens)
            else:
                raise ValueError("No handler for %s" % token.type)
            if value:
                values.append(value)

        if len(values) == 1:
            return values[0], tokens

        return Tree(values), tokens

    def eat(self, type, tokens):
        """Attempts to eat a token of the given type, removing it from
        tokens.
        """
        token = tokens[0]
        if token.type == type:
            return True, tokens[1:]
        return False, tokens

    def eat_consecutive(self, type, tokens):
        """Continuously eats all tokens of the given type, removing them from
        tokens.
        """
        while True:
            eaten, tokens = self.eat(type, tokens)
            if not eaten:
                break
        return tokens

    def parse_string(self, tokens):
        token = tokens[0]
        assert token.type == T_STRING
        return token.value, tokens[1:]

    def parse_ws(self, tokens):
        token = tokens[0]
        assert token.type == T_WS
        return token.value, tokens[1:]

    def parse_lookup(self, tokens):
        token = tokens[0]
        assert token.type == T_LOOKUP_START

        type, tokens = self.parse_string(tokens[1:])

        # We don't care about whitespace between the lookup type and value.
        tokens = self.eat_consecutive(T_WS, tokens)

        value, tokens = self.parse_value(tokens)

        lookup = Lookup(type, value)
        return lookup, tokens[1:]
