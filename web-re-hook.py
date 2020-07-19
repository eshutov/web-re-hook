#!/usr/bin/env python3

import argparse
import re
import yaml
import logging
import sys
import json
import validators
import py_compile
import os
import asyncio
import jinja2
import aiohttp
from aiohttp import web, ClientSession


def load_yml(file):
    with open(file, 'r') as f:
        try:
            yml = yaml.safe_load(f)
        except yaml.YAMLError:
            logging.error(f'load_yml: Broken yml format in {file}. Exiting.')
            return(False)
        except:
            logging.error('load_yml: Unexpected yml error:', sys.exc_info()[0])
            return(False)

    return(yml)

def get_json_params(json_query):
    output = []
    shift = 0
    query_len = len(json_query)

    while shift < query_len:
        match = re.match(json_dict_pattern, json_query[shift:query_len])
        if match:
            output.append(match.expand('\g<2>'))
            shift += match.span(1)[1]
            continue

        match = re.match(json_list_pattern, json_query[shift:query_len])
        if match:
            output.append(int(match.expand('\g<2>')))
            shift += match.span(1)[1]
            continue

        logging.error(f'get_json_params: Cannot parse {json_query}. Exiting.')
        return(None)

    return(output)

def parse_when(when):
    output = []
    shift = 0
    when_len = len(when)

    while shift < when_len:
        match = re.match(allowed_words_pattern, when[shift:when_len])
        if match:
            output.append(match.expand('\g<1>'))
            shift += match.span(1)[1] + 1
            continue

        match = re.match(json_pattern, when[shift:when_len])
        if match:
            json_query = match.expand('\g<2>')
            json_params = get_json_params(json_query)
            if json_params is None:
                return(None)
            output.append(
                f'json_query_recussive(JSON, {json.dumps(json_params)})')
            shift += match.span(1)[1] + 1
            continue

        logging.error(
            f'parse_when: Cannot parse {when[shift:when_len]}. Exiting.')
        return(None)

    return(" ".join(output))

def json_query_recussive(JSON, json_items):
    obj = JSON

    try:
        while json_items:
            json_item = json_items.pop(0)
            if isinstance(json_item, str) and isinstance(obj, dict):
                obj = obj.get(json_item)
            elif isinstance(json_item, int) and isinstance(obj, list) and \
                    json_item < len(obj):
                obj = obj[json_item]
            else:
                logging.debug(
            f'json_query_recussive: Type not match in {json_items}. Exiting.')
                return(None)
    except ValueError:
        logging.error(
            f'json_query_recussive: Value error in {json_items}. Exiting.')
        return(None)
    except TypeError:
        logging.error(
            f'json_query_recussive: Type error in {json_items}. Exiting.')
        return(None)
    except:
        logging.error(
            'json_query_recussive: JSON unexpected error:', sys.exc_info()[0])
        return(None)

    return(obj)

def prepare_rules(rules, routes, template_path):
    templates = {}

    for rule in rules:
        if not rule.get('name'):
            logging.error(
                f'prepare_rules: Missed name field in {rule}. Exiting')
            return(False, False)

        if rule.get('when'):
            parsed_when = parse_when(rule['when'])
            if parsed_when is None:
                return(False, False)
            try:
                code = compile((parsed_when), 'string', 'eval')
            except SyntaxError:
                logging.error(
                    f"prepare_rules: Syntax error in {rule['when']}. Exiting.")
                return(False, False)
            except py_compile.PyCompileError:
                logging.error(
                    f"prepare_rules: Compile error in {rule['when']}. Exiting.")
                return(False, False)
            except:
                logging.error(
                "prepare_rules: Unexpected compile error in {rule['when']}:",
                              sys.exc_info()[0])
                return(False, False)
            rule.update({'when': code})

        if rule.get('routes'):
            for route in rule['routes']:
                if route not in routes.keys():
                    logging.error(
                    f'prepare_rules: {route} is absent in routes.yml. Exiting.')
                    return(False, False)
        else:
            logging.error(
                f'prepare_rules: Route is not set for {rule["name"]}. Exiting.')
            return(False, False)

        if rule.get('template'):
            if rule['template'] not in templates.keys():
                path = template_path + rule['template']
                if not os.path.isfile(path) or not os.access(path, os.R_OK):
                    logging.error(
                        f'prepare_rules: Something wrong with {path}. Exiting.')
                    return(False, False)
                with open(path, 'r') as f:
                    try:
                        j2template = jinja2.Template(f.read())
                    except jinja2.TemplateError:
                        logging.error(
             f"prepare_rules: Jinja template error in {rule['name']}. Exiting.")
                        return(False, False)
                    templates.update({rule['template']: j2template})
        else:
            logging.error(
            f'prepare_rules: Template is not set for {rule["name"]}. Exiting.')
            return(False, False)

        if 'done' in rule.keys():
            if rule['done'] not in [True, False]:
                logging.error(
                    f'prepare_rules: Wrong done in {rule["name"]}. Exiting.')
                return(False, False)
        else:
            rule.update({'done': done})

    return(rules, templates)

def check_routes(routes):
    for key, value in routes.items():
        if not validators.url(value):
            logging.error(
                f'check_routes: {key, value} url validation failed. Exiting.')
            return(False)
    return(True)

async def receive_handler(request):
    text = await request.text()
    none = None
    try:
        json_received = json.loads(text)
    except ValueError:
        logging.error(f'receive_handler: Broken JSON format: {x_headers}')
        raise web.HTTPOk
    except:
        logging.error("receive_handler: JSON Unexpected error:",
                     sys.exc_info()[0])
        raise web.HTTPOk

    app_config = request.app['app_config']
    routes = app_config['routes']
    rules = app_config['rules']
    templates = app_config['templates']
    arguments = app_config['arguments']
    headers = request.headers

    asyncio.create_task(process_rules(
            routes, rules, templates, arguments, json_received, headers))

    raise web.HTTPOk

async def send_handler(JSON, url, name, template, arguments):
    text = template.render(JSON = JSON)
    try:
        json_ = json.loads(text)
    except ValueError:
        logging.warning(f'send_handler: Broken JSON format in {name}')
        return(None)
    except:
        logging.warning(f'send_handler: Unexpected JSON error in {name}:',
                     sys.exc_info()[0])
        return(None)

    i = 0
    tries = arguments[TRIESARG]
    while i < tries:
        async with ClientSession() as session:
            try:
                async with session.post(url, json=json_) as resp:
                    data = await resp.text()
                    if resp.status >= 200 and resp.status < 300:
                        return(None)
                    else:
                        logging.debug(
                            f"send_handler: rule '{name}' received: {data}")
            except aiohttp.ClientError:
                logging.error(
                    f"send_handler: HTTP client error in '{name}' rule:",
                    sys.exc_info()[0])
        i += 1
        await asyncio.sleep(arguments[RETRYDELAY])

async def process_rules(routes, rules, templates, arguments, JSON, headers):
    for rule in rules:

# match headers
        upper_break = False
        for key, value in rule.get('headers', {}).items():
            if headers.get(key) and headers[key] == value:
                continue
            else:
                upper_break = True
                break
        if upper_break:
            break

# match when conditions
        try:
            when_matched = eval(rule['when'])
        except ValueError:
            logging.error(
                f"process_rules: Value error in {rule['name']}. Exiting.")
            continue
        except TypeError:
            logging.error(
                f"process_rules: Type error in {rule['name']}. Exiting.")
            continue
        except:
            logging.error(
                "process_rules: Unexpected error in {rule['name']}:",
                sys.exc_info()[0])
            continue
        if not when_matched:
            logging.info(f"process_rules: Not matched '{rule['name']}' rule")
            continue

        logging.info(f"process_rules: Matched '{rule['name']}' rule")
        for route in rule['route']:
            asyncio.create_task(send_handler(JSON, routes[route],
                        rule['name'], templates[rule['template']], arguments))

        if rule["done"]:
            break

def get_arguments():
    output = {}

    parser = argparse.ArgumentParser(description=ARGSPARSEDESC)
    for item in ARGSTOPARSE:
        name = '--' + item["name"]
        default = item["default"]
        help_ = item["help"] + f" (default: {default})"
        parser.add_argument(name, default=default, help=help_)
    parsed_args = vars(parser.parse_args())

    for item in ARGSTOPARSE:
        name = item["name"]
        default = item["default"]
        env_value = os.environ.get(name.upper(), default)
        arg_value = parsed_args[name]
        value = env_value
        if arg_value != default:
            value = arg_value

        if name == CONFDIRARG:
            if value[-1] != '/':
                value += '/'

        output.update({name: value})

    return(output)


# CONSTS
allowed_words = ['True', 'False', '\d+', '\'[\w ]*\'',
                 'and', 'or', 'not',
                 'in', 'is',
                 '>', '<', '==',
                 '>=', '<=',
                 ]
allowed_words_pattern = re.compile(
                        f'^([\(\)\s]*(?:{"|".join(allowed_words)})[\(\)\s]*?)')
json_pattern = re.compile('^([\(\)\s]*JSON((?:\[[^\[\]]+\])+)[\(\)\s]*?)')
json_list_pattern = re.compile('^(\[(\d+)\])')
json_dict_pattern = re.compile('^(\[[\'\"](\w+)[\'\"]\])')

ARGSPARSEDESC ='Webhooks re-sender'
CONFDIRARG = 'confdir'
PORTARG = 'port'
RETRYDELAY = 'delay'
TRIESARG = 'tries'
ARGSTOPARSE = [
    {"name": CONFDIRARG,
     "default": "./",
     "help": "path to confdir"},
    {"name": PORTARG,
     "default": 8080,
     "help": "port to listen"},
    {"name": "done",
     "default": True,
     "help": "done when first rule match"},
    {"name": RETRYDELAY,
     "default": 5,
     "help": "retry delay seconds"},
    {"name": TRIESARG,
     "default": 1,
     "help": "max amount of send attemps"}
    ]

logging.basicConfig(level=logging.INFO)

# void main(void)
arguments = get_arguments()
if len(arguments) != len(ARGSTOPARSE):
    logging.error(f"main: Args parse error. Exiting.")
    sys.exit(1)

routes = load_yml(f"{arguments[CONFDIRARG]}routes.yml")
if routes == False:
    sys.exit(1)

if check_routes(routes) == False:
    sys.exit(1)

rules = load_yml(f"{arguments[CONFDIRARG]}rules.yml")
if rules == False:
    sys.exit(1)

template_path = f"{arguments[CONFDIRARG]}templates/"
rules, templates = prepare_rules(rules, routes, template_path)
if False in (rules, templates):
    sys.exit(1)

app = web.Application()
app.add_routes([web.post('/', receive_handler)])
app_config = {'routes': routes,
              'rules': rules,
              'templates': templates,
              'arguments': arguments}
app['app_config'] = app_config
web.run_app(app, port=arguments[PORTARG])

