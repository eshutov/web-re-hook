#!/usr/bin/env python3
import pytest
from webrehook import *

@pytest.fixture(scope="function", params=[
    ({'a': 'eherhejtyj/ewreh/erh'}, False),
    ({'a': 'ya.ru/wewg/utuk?name=ferret&color=purple'}, False),
    ({'a': 'http://eherhejtyj/ewreh/erh'}, False),
    ({'a': 'http://ya.ru/wewg/utuk?name=ferret&color=purple'}, True),
    ({'a': 'https://eherhejtyj/ewreh/erh'}, False),
    ({'a': 'https://ya.ru/wewg/utuk?name=ferret&color=purple'}, True),
    ])
def param_check_routes(request):
    return request.param

def test_check_routes(param_check_routes):
    (input_data, expected_output) = param_check_routes
    result = check_routes(input_data)
    assert result == expected_output

@pytest.fixture(scope="function", params=[
    ('["test"]', ["test"]),
    ('[\'test\']', ["test"]),
    ('["test"][0]', ["test", 0]),
    ('["test"]["0"]', ["test", "0"]),
    ('["test1"][0]["test2"]', ["test1", 0, "test2"]),
    ('["test1"][0]["test2"]["0"]', ["test1", 0, "test2", "0"]),
    ('["test]', False),
    ('[test]', False),
    ('["test"]["test]', False),
    ('[0_]', False),
    ('["test"][0_]', False),
    ('[["test"]', False),
    ('["test"]]', False),
    ('[["test"][0]', False),
    ('[[0]["test"]', False),
    ('["test"]][0]', False),
    ('["test"][0]]', False)
    ])
def params_get_json_params(request):
    return request.param

def test_get_json_params(params_get_json_params):
    (input_data, expected_output) = params_get_json_params
    result = get_json_params(input_data)
    assert result == expected_output

@pytest.fixture(scope="function", params=[
#   ('''JSON["user_name"] == "John Smith"''',
#       """json_query_recussive(JSON, ["user_name"]) == 'John Smith'"""),
    ("""JSON['user_name'] == 'John Smith'""",
        """json_query_recussive(JSON, ["user_name"]) == 'John Smith'"""),
    ("""JSON['project']['name'] == 'Diaspora'""",
        """json_query_recussive(JSON, ["project", "name"]) == 'Diaspora'""")
    ])
def params_parse_when(request):
    return request.param

def test_parse_when(params_parse_when):
    (input_data, expected_output) = params_parse_when
    result = parse_when(input_data)
    assert result == expected_output

def prepare_testdata():
    testdata = []

    yaml_input = load_yml('rules.yml')
    yaml_output = load_yml('rules.yml')
    if yaml_input == False or yaml_output == False or \
            len(yaml_input) != len(yaml_output):
        return([{"input": False, "output": True}])

    for input_, output in zip(yaml_input, yaml_output):
        testdata.append({"input": input_, "output": output})

    return(testdata)

@pytest.fixture(scope="function", params=prepare_testdata())
def params_test_params(request):
    return request.param

def test_params(params_test_params):
    input_data, expected_output = params_test_params["input"], params_test_params["output"]
    assert input_data == expected_output



