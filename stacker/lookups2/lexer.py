import re
from collections import namedtuple


# Token types
T_LOOKUP_START = "LOOKUP_START"
T_LOOKUP_END = "LOOKUP_END"
T_CHAR = "CHAR"
T_STRING = "STRING"
T_WS = "WHITESPACE"


# Regular expression rules to match a string of characters to a token.
RULES = [
    (re.compile("\${"), T_LOOKUP_START),
    (re.compile("}"),   T_LOOKUP_END),
    (re.compile("\s+"), T_WS),
]


Token = namedtuple("Token", ("type", "value"))


class Lexer(object):
    """Lexical analyzer (also known as scanner or tokenizer)

    This method is responsible for breaking a sentence
    apart into tokens. One token at a time.
    """

    def __init__(self, text):
        self.text = text
        self.pos = 0

    def next_token(self):
        text = self.text
        if self.pos >= len(text):
            return None

        for regex, type in RULES:
            m = regex.match(text, self.pos)
            if m:
                self.pos = m.end()
                return Token(type, m.group(0))

        token = Token(T_CHAR, text[self.pos])
        self.pos += 1
        return token

    def tokens(self):
        while True:
            token = self.next_token()

            # Compact consecutive T_CHAR to T_STRING.
            if token and token.type == T_CHAR:
                value = ""
                while token and token.type == T_CHAR:
                    value += token.value
                    token = self.next_token()
                yield Token(T_STRING, value)

            if not token:
                break

            yield token
