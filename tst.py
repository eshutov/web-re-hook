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
    tokens = { SUBSTR, JSON, NUMBER, BINOP, BINOPEXC, NOT, IN }
    literals = { '(', ')', '[', ']', '\'', '"' }
    ignore = ' \t'
    ignore_comment = r'\#.*'
    BINOP  = r'\+|-|\*|/|==|<=|<|>=|>|!='
    SUBSTR = r'[a-zA-Z_][a-zA-Z0-9_]*'
    SUBSTR['JSON'] = JSON
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
    tokens = MyLexer.tokens

    def __init__(self):
        json_query = []

    @_('"(" expr ")"')
    def expr(self, p):
        return f'{p[0]}{p.expr}{p[2]}'

    @_('expr binop string')
    def expr(self, p):
        return f'{p.expr} {p[1]} {p.string}'

    @_('expr binop expr')
    def expr(self, p):
        return f'{p.expr0} {p[1]} {p.expr1}'

    @_('NOT expr')
    def expr(self, p):
        return f'not {p.expr}'

    @_('NOT IN')
    def binop(self, p):
        return f"{p[0]} {p[1]}"

    @_('json_query_recursive')
    def expr(self, p):
        return p[0]

    @_("json_query_recursive '[' string ']'")
    def json_query_recursive(self, p):
        self.json_query.append(p.string)
        return f"json_query_recursive{self.json_query}"

    @_('\'"\' SUBSTR \'"\'')
    def string(self, p):
        return f"{p.SUBSTR}"

    @_("\"'\" SUBSTR \"'\"")
    def string(self, p):
        return f"{p.SUBSTR}"

    @_("json_query_recursive '[' NUMBER ']'")
    def json_query_recursive(self, p):
        self.json_query.append(p.NUMBER)
        return f"json_query_recursive{self.json_query}"

    @_('JSON')
    def json_query_recursive(self, p):
        self.json_query = []
        return 'json_query_recursive'

    @_('NUMBER')
    def expr(self, p):
        return int(p.NUMBER)

    @_('BINOPEXC')
    def binop(self, p):
        return p.BINOPEXC

    @_('BINOP')
    def binop(self, p):
        return p.BINOP

if __name__ == '__main__':
    whentxt = "(JSON['outer'] == 'Outer' and (JSON['inner'] == 'Inner'))"
    #whentxt = "JSON['outer'] == 'Outer' and (JSON['inner'] == 'Inner')"
    #and (JSON['inner'] == 'Inner')"
    #whentxt = "JSON['outer'] == 'Outer'"
    #whentxt = '(JSON[0]["abc"][\'qwe\'] == 123) not in 1'

    lexer = MyLexer()
    parser = MyParser()
#   for tok in lexer.tokenize(whentxt):
#       print(tok)

    print("#########")
    result = parser.parse(lexer.tokenize(whentxt))
    print(result)
