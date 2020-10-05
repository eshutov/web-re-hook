#!/usr/bin/env python3

import argparse
import re
import yaml
import logging
import sys
import json
import os
from collections import Counter
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
            "python3 webrehook.py --confdir testdata/integration/ --autodone False",
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
        self.received = {}

    async def runner(self):
        self.app = web.Application()
        self.app.add_routes([
            web.post('/{path}', self.receive_handler)])

        self.apprunner = web.AppRunner(self.app)
        await self.apprunner.setup()
        self.site = web.TCPSite(self.apprunner, 'localhost', self.port)
        try:
            await self.site.start()
        except OSError:
            logging.error(f'site.start: OSError')
            return(False)
        return(True)

    @classmethod
    async def run(cls, port=8081):
        obj = cls(port)
        if await obj.runner():
            return obj
        return(False)

    async def shutdown(self):
        await self.apprunner.cleanup()

    async def receive_handler(self, request):
        text = await request.text()
        none = None
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

        path = request.match_info['path']
        if list_ := self.received.get(path):
            list_.append(json_received)
        else:
            list_ = [json_received]
        self.received.update({path: [json_received]})

        raise web.HTTPOk

    def get_received(self):
        return(self.received)

    def reset(self):
        self.received = {}

async def send_(test):
    async with ClientSession() as session:
        try:
            async with session.post(
                    f'http://localhost:8080', json=test['data'],
                    headers=test['headers']) as resp:
                if resp.status != 200:
                    logging.error(f"main: response code is not 200")
                    return(False)
        except aiohttp.ClientError:
            logging.error(
                f"main: ClientError exception with {test['name']}:",
                sys.exc_info()[0])
            return(False)
    return(True)

async def main():
    logging.basicConfig(level=logging.INFO)

    tests = load_yml('testdata/integration/testdata.yml')
    if not tests:
        logging.error("main: testdata loading error")
        sys.exit(1)

    for test in tests:
        for key, value in test["mapping"].items():
            if max(value) >= len(test["received"]):
                logging.error(
                    f"main: Test {test['name']} in {key} path out of index")
                sys.exit(1)

    wrh_runner = await WRHRunner().run()
    if wrh_runner == False:
        logging.error("main: Cannot start child process.")
        await do_exit(wrh_runner)
        sys.exit(1)

    web_server_runner = await WebServerRunner.run()
    if web_server_runner == False:
        logging.error("main: Cannot start web server.")
        await do_exit(wrh_runner, web_server_runner)
        sys.exit(1)

# Give child script time to run python or/and die with runtime errors
    await asyncio.sleep(1)
    if not wrh_runner.running:
        logging.error("Child script error")
        logging.error(f"stdout: {wrh_runner.stdout}")
        logging.error(f"stderr: {wrh_runner.stderr}")
        await do_exit(wrh_runner, web_server_runner)
        sys.exit(1)

# Main test cycle
    for test in tests:
        print("################################")
        test_failed = False
        testname = test['name']
        logging.info(f"Tesing: {testname}")
        web_server_runner.reset()
        await send_(test)

        received_expected = {}
        mapping = test["mapping"]
        for path, indexes in mapping.items():
            logging.info(f"Checking: {path}")
            received_expected_path = []
            for index in indexes:
                received_expected_path.append(test["received"][index])
            received_expected.update({path: received_expected_path})
# Give child script time to resend hooks and us to receive them
        await asyncio.sleep(1)
        received_actually = web_server_runner.get_received()
# We have both expected and actually received dicts here.
# Comparison of those dicts (key by key (path) comparing values
# (list of received jsons) using collections.Counter) begins below.
        pathes = list(set().union(*([mapping.keys(),
                                    received_actually.keys()])))
        for path in pathes:
            expected_hashable = list(map(
                            json.dumps, received_expected.get(path, [])))
            actually_hashable = list(map(
                            json.dumps, received_actually.get(path, [])))
            expected_counter = Counter(expected_hashable)
            actually_counter = Counter(actually_hashable)

            if expected_counter == actually_counter:
                continue

            test_failed = True
            logging.info(f'Path failed: "{testname}" /{path}')
            excess_data = list(actually_counter - expected_counter)
            if len(excess_data) > 0:
                for item in excess_data:
                    logging.info(f"Not expected but received:\n{item}")
            missed_data = list(expected_counter - actually_counter)
            if len(missed_data) > 0:
                for item in missed_data:
                    logging.info(f"Expected but not received:\n{item}")

        if test_failed:
            logging.info(f'TEST FAILED: "{testname}"')
        else:
            logging.info(f'TEST SUCCESSFUL: "{testname}"')

    await asyncio.sleep(600)
    await do_exit(wrh_runner, web_server_runner)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

