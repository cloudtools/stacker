from stacker.lookups2.parser import Parser
from stacker.lookups2.parser import (
    Tree,
    Lookup,
)

from stacker.lookups2.lexer import (
    Token,
    T_STRING,
    T_WS,
    T_LOOKUP_START,
    T_LOOKUP_END,
)

PARSER_TESTS = [
    (
        [
            Token(T_STRING, "world")],
        "world"),
    (
        [
            Token(T_STRING, "hello"),
            Token(T_WS, " "),
            Token(T_STRING, "world")],
        Tree(["hello", " ", "world"])),
    (
        [
            Token(T_LOOKUP_START, "${"),
            Token(T_STRING, "output"),
            Token(T_WS, " "),
            Token(T_STRING, "vpc::Id"),
            Token(T_LOOKUP_END, "}")],
        Lookup("output", "vpc::Id")),
    (
        [
            Token(T_LOOKUP_START, "${"),
            Token(T_STRING, "noop"),
            Token(T_WS, " "),
            Token(T_LOOKUP_START, "${"),
            Token(T_STRING, "output"),
            Token(T_WS, " "),
            Token(T_STRING, "stack::Output"),
            Token(T_LOOKUP_END, "}"),
            Token(T_STRING, ","),
            Token(T_LOOKUP_START, "${"),
            Token(T_STRING, "output"),
            Token(T_WS, " "),
            Token(T_STRING, "stack::Output2"),
            Token(T_LOOKUP_END, "}"),
            Token(T_LOOKUP_END, "}")],
        Lookup(
            "noop",
            Tree([
                Lookup("output", "stack::Output"),
                ",",
                Lookup("output", "stack::Output2")]))),
]


def test_parser():
    for test in PARSER_TESTS:
        tokens, ast = test
        yield ParserTest(tokens, ast)


class ParserTest(object):
    def __init__(self, tokens, ast):
        self.tokens = tokens
        self.ast = ast
        self.description = "Parser(%s)" % tokens

    def __call__(self):
        parser = Parser(self.tokens)
        ast = parser.parse()
        print ast
        assert ast == self.ast
