import unittest

from stacker.lookups2.lexer import Lexer, Token
from stacker.lookups2.lexer import (
    T_LOOKUP_START,
    T_LOOKUP_END,
    T_STRING,
    T_WS,
)


LEXER_TESTS = [
    (
        "hello world",
        [
            Token(T_STRING, "hello"),
            Token(T_WS, " "),
            Token(T_STRING, "world")]),
    (
        "${output vpc::Id}",
        [
            Token(T_LOOKUP_START, "${"),
            Token(T_STRING, "output"),
            Token(T_WS, " "),
            Token(T_STRING, "vpc::Id"),
            Token(T_LOOKUP_END, "}")]),
    (
        "url://${output fakeStack::FakeOutput}@",
        [
            Token(T_STRING, "url://"),
            Token(T_LOOKUP_START, "${"),
            Token(T_STRING, "output"),
            Token(T_WS, " "),
            Token(T_STRING, "fakeStack::FakeOutput"),
            Token(T_LOOKUP_END, "}"),
            Token(T_STRING, "@")]),
    (
        "${noop ${output stack::Output},${output stack::Output2}}",
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
            Token(T_LOOKUP_END, "}")]),
]


def test_lexer():
    for test in LEXER_TESTS:
        input, tokens = test
        yield LexerTest(input, tokens)


class LexerTest(object):
    def __init__(self, input, tokens):
        self.input = input
        self.tokens = tokens
        self.description = "Lexer(%s)" % input

    def __call__(self):
        lexer = Lexer(self.input)
        tokens = [token for token in lexer.tokens()]
        assert tokens == self.tokens


class TestToken(unittest.TestCase):
    def test_cmp(self):
        self.assertEqual(
            Token(T_LOOKUP_START, "${"),
            Token(T_LOOKUP_START, "${"))
