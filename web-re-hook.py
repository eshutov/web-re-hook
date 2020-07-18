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

def prepare_rules(rules, routes):
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

        if rule.get('route'):
            for route in rule['route']:
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
            rule.update({'done': done_deafults})

    return(rules, templates)

def check_routes(routes):
    for key, value in routes.items():
        if not validators.url(value):
            logging.error(f'{key, value} url validation failed. Exiting.')
            return(False)

async def receive_handler(request):
    x_headers = get_x_headers(request)

    text = await request.text()
    none = None
    try:
        json_received = json.loads(text)
    except ValueError:
        logging.error(f'Broken JSON format: {x_headers}')
        raise web.HTTPOk
    except:
        logging.error("JSON Unexpected error:", sys.exc_info()[0])
        raise web.HTTPOk

    app_config = request.app['app_config']
    routes = app_config['routes']
    rules = app_config['rules']
    templates = app_config['templates']

    asyncio.create_task(process_rules(
            routes, rules, templates, json_received, x_headers))

    raise web.HTTPOk

def get_x_headers(request):
    x_headers = {}
    headers = request.headers.keys()
    for header in headers:
        if header[0:2] == 'X-':
            x_headers.update({header: request.headers.get(header)})

    return(x_headers)


async def send_handler(JSON, url, template, name):
    text = template.render(JSON = JSON)
    try:
        json_ = json.loads(text)
    except ValueError:
        logging.error(f'Broken JSON format in {name}')
        return()
    except:
        logging.error(f"Unexpected JSON error in {name}:", sys.exc_info()[0])
        return()

    i = 0
    while i < TRIES:
        async with ClientSession() as session:
            try:
                async with session.post(url, json=json_) as resp:
                    data = await resp.text()
                    if resp.status >= 200 and resp.status < 300:
                        break
                    else:
                        if data:
                            logging.info(f"Rule {name} received: {data}")
            except aiohttp.ClientError:
                logging.error(f"HTTP client error in {name}:",
                              sys.exc_info()[0])
                continue
        i += 1
        await asyncio.sleep(10)

async def process_rules(routes, rules, templates, JSON, x_headers):
    for rule in rules:
        if 'x-header' in rule.keys():
            for x_header in rule['x-header']:
                if x_header not in x_headers:
                    continue

        try:
            when_match = eval(rule['when'])
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
        if not when_match:
            continue

        for route in rule['route']:
            asyncio.create_task(send_handler(JSON, routes[route],
                        templates[rule['template']], rule['name']))

        if rule["done"]:
            break

# void main(void)

TRIES = 2
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

parser = argparse.ArgumentParser(description='Webhooks re-sender')
parser.add_argument('--path', default="./",
                    help='path to workdir (default: pwd)')
parser.add_argument('--port', default=8080,
                    help='port to listen (default: 8080)')
parser.add_argument('--done', default=True,
                    help='done when first rule match (default: True)')
parse_args = vars(parser.parse_args())
path = parse_args['path']
port = parse_args['port']
done_deafults = parse_args['done']
template_path = f'{path}templates/'


logging.basicConfig(level=logging.INFO)

routes = load_yml(f"{path}routes.yml")
if routes == False:
    sys.exit(1)
if check_routes(routes) == False:
    sys.exit(1)
rules_raw = load_yml(f"{path}rules.yml")
if rules_raw == False:
    sys.exit(1)
rules, templates = prepare_rules(rules_raw, routes)
if False in (rules, templates):
    sys.exit(1)

#print(routes)
#print(rules)
#print(templates)
app_config = {'routes': routes, 'rules': rules, 'templates': templates}

app = web.Application()
app.add_routes([web.post('/', receive_handler)])
app['app_config'] = app_config
web.run_app(app, port=port)

