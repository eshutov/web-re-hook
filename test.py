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
# using '"' as str border
    ('JSON["user_name"] == "John Smith"',
        "json_query_recursive(JSON, ['user_name']) == 'John Smith'"),
# excess and missed spaces
    (" (   JSON[  'user_name' ]    =='John Smith' )  ",
        "(json_query_recursive(JSON, ['user_name']) == 'John Smith')"),
# extra-long query with almost whole syntax
    ("((JSON['commits'][0] is not None) and (JSON['commits'][0]['author']['name'] == 'Jordi Mallach')) or (False in JSON['false'] and True not in JSON['false'])",
        "((json_query_recursive(JSON, ['commits', 0]) is not None) and (json_query_recursive(JSON, ['commits', 0, 'author', 'name']) == 'Jordi Mallach')) or (False in json_query_recursive(JSON, ['false']) and True not in json_query_recursive(JSON, ['false']))"),
# broken queries
    ("JSON[['user_name'] == 'John Smith'", None),
    ("JSON['user_name']] == 'John Smith'", None),
    ("JSON[''user_name'] == 'John Smith'", None),
    ("JSON[''user_name']' == 'John Smith'", None),
    ("JSON['user_name'][] == 'John Smith'", None),
    ("JSON['user_name']() == 'John Smith'", None),
    ("(JSON['user_name'] == 'John Smith'", None),
    ("JSON['user_name']) == 'John Smith'", None),
    ("JSON['user_name'] (==) 'John Smith'", None),
    ("JSON['user_name'] '==' 'John Smith'", None),
    ("JSON['user_name'] == 'John()Smith'", None),
    ("(JSON['user_name'] == 'John)Smith'", None),
    ])
def params_parse_when(request):
    return request.param

def test_parse_when(params_parse_when):
    (input_data, expected_output) = params_parse_when
    result = parse_when(input_data)
    assert result == expected_output

@pytest.fixture(scope="function", params=[
    ([], [0], None),
    ([0], [], None),
    ([1], ["0"], None),
    ([1], [0], 1),
    ([1, [11]], [1, 0], 11),
    ([1, [11]], [1, 1], None),
    ({'a': 'aa', 'b': 'bb'}, [0], None),
    ({'a': 'aa', 'b': 'bb'}, ['b'], 'bb'),
    ({'a': 'aa', 'b': {'bb': 'bbb'}}, ['b', 'bb'], 'bbb'),
    ({'a': [0, 1]}, ['a', 1], 1),
    ([{'a': 'aa'}], [0, 'a'], 'aa')
    ])
def params_json_query_recursive(request):
    return request.param

def test_json_query_recursive(params_json_query_recursive):
    (input_json, input_query, expected_output) = \
        params_json_query_recursive
    result = json_query_recursive(input_json, input_query)
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

@pytest.mark.skip(reason="File rules parser reserved for future use")
def test_params(params_test_params):
    input_data, expected_output = \
        params_test_params["input"], params_test_params["output"]
    assert input_data == expected_output

