#!/usr/bin/env python3

from sly import Lexer, Parser
from sly.yacc import GrammarError
from sly.lex import LexError
import logging

class WhenLexer(Lexer):
    tokens = { NAME, STRING, JSON, NUMBER, BINOP, BINOPEXC, NOT, IN, RESWORD }
    literals = { '(', ')', '[', ']', '\'', '"' }
    ignore = ' \t'
    ignore_comment = r'\#.*'
    BINOP  = r'\+|-|\*|/|==|<=|<|>=|>|!='
    NAME = r'[a-zA-Z_][a-zA-Z0-9_]*'
    NAME['JSON'] = JSON
    NAME['True'] = RESWORD
    NAME['False'] = RESWORD
    NAME['None'] = RESWORD
    NAME['and'] = BINOPEXC
    NAME['or'] = BINOPEXC
    NAME['is'] = BINOPEXC
    NAME['in'] = IN
    NAME['not'] = NOT

    @_(r'\d+')
    def NUMBER(self, t):
        t.value = int(t.value)
        return t

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    @_(r'(?:"[a-zA-Z0-9_ ]+")|(?:\'[a-zA-Z0-9_ ]+\')')
    def STRING(self, t):
        if t.value[0] == '"':
            t.value = f"'{t.value[1:-1]}'"
        return t

    def error(self, t):
        logging.error('Line %d: Bad character %r' % (self.lineno, t.value[0]))
        raise LexError(
            'Line %d: Bad character %r' % (self.lineno, t.value[0]),
            self.text, t.index)

class WhenParser(Parser):
#   debugfile = 'parser.out'
    tokens = WhenLexer.tokens
# precedance does not make sence here: since we do not do calcultaions,
# but just checking syntax, it is here to rm shift/reduce error only
    precedence = (
       ('left', NAME, STRING, JSON, NUMBER, BINOP, BINOPEXC, NOT, IN, RESWORD),
    )

    def __init__(self):
        json_query = []

    def error(self, token):
        if token:
            lineno = getattr(token, 'lineno', 0)
            if lineno:
                logging.error(
                    f'sly: Syntax error at line {lineno}, token={token.type}')
                raise GrammarError
            else:
                logging.error(f'sly: Syntax error, token={token.type}')
                raise GrammarError
#       else:
#           logging.error('sly: Parse error in input. EOF')
#           raise GrammarError

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
        return f"json_query_recursive(JSON, [{', '.join(map(str, self.json_query))}])"

    @_('JSON')
    def json_query_recursive(self, p):
        self.json_query = []
        return 'json_query_recursive'

    @_('STRING')
    def expr(self, p):
        return p.STRING

    @_('RESWORD')
    def expr(self, p):
        return p.RESWORD

    @_('NUMBER')
    def expr(self, p):
        return p.NUMBER

    @_('NAME')
    def expr(self, p):
        return p.NAME

def main(txt):
    lexer = WhenLexer()
    try:
        tokens = lexer.tokenize(txt)
    except LexError:
        logging.error(
            f'parse_when: Unable to lex {txt}. Exiting.')
        return(None)
    except:
        logging.error(
            'parse_when: Lex unexpected error:', sys.exc_info()[0])
        return(None)

# Very weird these 2 lines below break parser when active
#   for token in tokens:
#       print(token)

    parser = WhenParser()
    try:
        result = parser.parse(tokens)
    except GrammarError:
        logging.error(
            f'parse_when: Unable to parse {txt}. Exiting.')
        return(None)
    except:
        logging.error(
            'parse_when: Parse unexpected error:', sys.exc_info()[0])
        return(None)
    return(result)

if __name__ == '__main__':
    print(main("((JSON['commits'][0] is not None) and (JSON['commits'][0]['author']['name'] == 'Jordi Mallach'))"))

