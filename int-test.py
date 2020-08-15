#!/usr/bin/env python3

import argparse
import re
import yaml
import logging
import sys
import json
import os
import asyncio
import aiohttp
from aiohttp import web, ClientSession
from whenparse import WhenLexer, WhenParser

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
        await asyncio.sleep(arguments[RETRYDELAYARG])

class WRHRunner():
    def __init__(self):
        self.running = False
        self.proc = None
        self.stdout = ""
        self.stderr = ""

    async def runner(self):
        if self.proc is not None:
            return(False)
        self.proc = await asyncio.create_subprocess_shell(
                            "python3 webrehook.py",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE)
        self.running = True
        asyncio.create_task(self.waiter())
        return(True)

    async def waiter(self):
        await self.proc.wait()
        self.running = False
        self.stdout, self.stderr = await self.proc.communicate()

    @classmethod
    async def run(cls):
        obj = cls()
        if result := await obj.runner():
            return(obj)
        return(False)

    async def shutdown(self):
        if not self.running:
            return()
        self.proc.kill()
        await asyncio.sleep(2)

        if not self.running:
            return()
        self.proc.terminate()

async def do_exit(wrh_runner=None, web_server_runner=None):
    tasks = []
    if wrh_runner:
        tasks.append(asyncio.create_task(wrh_runner.shutdown()))
    if web_server_runner:
        tasks.append(asyncio.create_task(web_server_runner.shutdown()))
    pass

class WebServerRunner():
    def __init__(self, port=8081):
        self.port = port

    async def runner(self):
        self.app = web.Application()
        self.app.add_routes([
            web.post('/{name}', self.receive_handler)])
        app_config = {'routes': '222'}
#       self.app['app_config'] = app_config

        self.runner_ = web.AppRunner(self.app)
        await self.runner_.setup()
        self.site = web.TCPSite(self.runner_, 'localhost', self.port)
        try:
            await self.site.start()
        except OSError:
            logging.error(f'site.start: OSError')
            return(False)
        return(True)

    @classmethod
    async def run(cls, port=8081):
        obj = cls(port)
        if result := await obj.runner():
            return obj
        return(False)

    async def shutdown(self):
        await self.runner_.cleanup()

    async def receive_handler(self, request):
        text = await request.text()
        none = None
#       print(request.match_info['name'])
        try:
            json_received = json.loads(text)
        except ValueError:
            logging.error(f'receive_handler: ValueError: {text}')
            raise web.HTTPOk
        except json.decoder.JSONDecodeError:
            logging.error(f'receive_handler: JSONDecodeError: {text}')
            raise web.HTTPOk
        except:
            logging.error("receive_handler: JSON Unexpected error:",
                         sys.exc_info()[0])
            raise web.HTTPOk

#       app_config = request.app['app_config']
        headers = request.headers
#       asyncio.create_task(process_rules(app_config, json_received, headers))

        raise web.HTTPOk

async def main():
    logging.basicConfig(level=logging.WARNING)

    wrh_runner = await WRHRunner().run()
    if wrh_runner == False:
        logging.error("Cannot start child process.")
        await do_exit(wrh_runner)
        sys.exit(1)

    web_server_runner = await WebServerRunner.run()
    if web_server_runner == False:
        logging.error("Cannot start web server.")
        await do_exit(wrh_runner, web_server_runner)
        sys.exit(1)

# Give child script time to run python or/and die with runtime errors
    await asyncio.sleep(2)
    if not wrh_runner.running:
        logging.error("Child script error:")
        logging.error(f"stdout: {wrh_runner.stdout}")
        logging.error(f"stderr: {wrh_runner.stderr}")
        await do_exit(wrh_runner, web_server_runner)
        sys.exit(1)

    await asyncio.sleep(60)
    await do_exit(wrh_runner, web_server_runner)


if __name__ == '__main__':
    try:
#       app = run_server()
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

