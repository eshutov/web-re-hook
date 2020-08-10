#!/usr/bin/env python3

import argparse
import re
import yaml
import logging
import sys
import json
import py_compile
import os
import asyncio
import jinja2
from sly import Lexer, Parser


class MyLexer(Lexer):
    tokens = { SUBSTR, JSON, NUMBER, BINOP, BINOPEXC, NOT, IN, RESWORD }
    literals = { '(', ')', '[', ']', '\'', '"' }
    ignore = ' \t'
    ignore_comment = r'\#.*'
    BINOP  = r'\+|-|\*|/|==|<=|<|>=|>|!='
    SUBSTR = r'[a-zA-Z_][a-zA-Z0-9_]*'
    SUBSTR['JSON'] = JSON
    SUBSTR['True'] = RESWORD
    SUBSTR['False'] = RESWORD
    SUBSTR['None'] = RESWORD
    SUBSTR['and'] = BINOPEXC
    SUBSTR['or'] = BINOPEXC
    SUBSTR['is'] = BINOPEXC
    SUBSTR['in'] = IN
    SUBSTR['not'] = NOT

    @_(r'\d+')
    def NUMBER(self, t):
        t.value = int(t.value)
        return t

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    def error(self, t):
        print('Line %d: Bad character %r' % (self.lineno, t.value[0]))
        self.index += 1

class MyParser(Parser):
    debugfile = 'parser.out'
    tokens = MyLexer.tokens
    precedence = (
       ('left', SUBSTR, JSON, NUMBER, BINOP, BINOPEXC, NOT, IN, RESWORD),
    )

    def __init__(self):
        json_query = []

    @_('"(" expr ")"')
    def expr(self, p):
        return f'{p[0]}{p.expr}{p[2]}'

    @_('expr BINOPEXC expr')
    def expr(self, p):
        return f'{p.expr0} {p[1]} {p.expr1}'

    @_('expr BINOP expr')
    def expr(self, p):
        return f'{p.expr0} {p[1]} {p.expr1}'

    @_('expr NOT IN expr')
    def expr(self, p):
        return f"{p[0]} {p[1]} {p[2]} {p[3]}"

    @_('expr IN expr')
    def expr(self, p):
        return f"{p[0]} {p[1]} {p[2]}"

    @_('NOT expr')
    def expr(self, p):
        return f'{p.NOT} {p.expr}'

    @_('json_query_recursive')
    def expr(self, p):
        return p[0]

    @_("json_query_recursive '[' expr ']'")
    def json_query_recursive(self, p):
        self.json_query.append(p.expr)
        return f"json_query_recursive[{', '.join(map(str, self.json_query))}]"

    @_('JSON')
    def json_query_recursive(self, p):
        self.json_query = []
        return 'json_query_recursive'

    @_('string')
    def expr(self, p):
        return p.string

    @_('RESWORD')
    def expr(self, p):
        return p.RESWORD

    @_('\'"\' SUBSTR \'"\'')
    def string(self, p):
        return f"'{p.SUBSTR}'"

    @_("\"'\" SUBSTR \"'\"")
    def string(self, p):
        return f"'{p.SUBSTR}'"

    @_('NUMBER')
    def expr(self, p):
        return p.NUMBER

if __name__ == '__main__':
    whentxt = "(JSON['outer'][0][\"qwe\"] == 'Outer' and (JSON['inner'] == 'Inner'))"

    lexer = MyLexer()
    parser = MyParser()
#   for tok in lexer.tokenize(whentxt):
#       print(tok)

    print("##########################################")
    result = parser.parse(lexer.tokenize(whentxt))
    print(result)
