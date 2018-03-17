from .lexer import Lexer
from .parser import Parser


def parse(text):
    lexer = Lexer(text)
    parser = Parser([token for token in lexer.tokens()])
    return parser.parse()
