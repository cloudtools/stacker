from stacker.lookups2 import parse
from stacker.lookups2.parser import (
    Tree,
    Lookup,
)

PARSE_TESTS = [
    (
        "world",
        "world"),
    (
        "hello world",
        Tree(["hello", " ", "world"])),
    (
        "hello   world",
        Tree(["hello", "   ", "world"])),
    (
        "${output vpc::Id}",
        Lookup("output", "vpc::Id")),
    (
        "${noop ${output stack::Output},${output stack::Output2}}",
        Lookup(
            "noop",
            Tree([
                Lookup("output", "stack::Output"),
                ",",
                Lookup("output", "stack::Output2")]))),
]


def test_parse():
    for test in PARSE_TESTS:
        text, ast = test
        yield ParseTest(text, ast)


class ParseTest(object):
    def __init__(self, text, ast):
        self.text = text
        self.ast = ast
        self.description = "parse(%s)" % text

    def __call__(self):
        ast = parse(self.text)
        assert ast == self.ast
