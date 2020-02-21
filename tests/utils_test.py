from http_types.types import HttpMethod, Protocol
from http_types.utils import ResponseBuilder, RequestBuilder
from io import StringIO
from os import path
import os
import json
from http_types import (
    HttpExchange,
    HttpExchangeBuilder,
    HttpExchangeReader,
    HttpExchangeWriter,
)
from dateutil.parser import isoparse
import jsonschema
from typeguard import check_type  # type: ignore

dir_path = os.path.dirname(os.path.realpath(__file__))
SAMPLE_JSON = path.join(dir_path, "resources", "sample.json")
SAMPLE_JSONL = path.join(dir_path, "resources", "sample.jsonl")
SCHEMA_PATH = path.join(dir_path, "resources", "http-types-schema.json")


def read_example():
    with open(SAMPLE_JSON) as f:
        content = f.read()
        return json.loads(content)


def read_schema():
    with open(SCHEMA_PATH) as f:
        content = f.read()
        return json.loads(content)


request_response_pair = read_example()


def test_typeguard():
    reqres = HttpExchangeBuilder.from_dict(request_response_pair)
    check_type("reqres", reqres, HttpExchange)


def test_request_from_dict():
    dict_req = {
        "host": "api.github.com",
        "protocol": "https",
        "method": "get",
        "pathname": "/v1/users",
        "query": {"a": "b", "q": ["1", "2"]},
    }
    req = RequestBuilder.from_dict(dict_req)
    assert req.method == HttpMethod.GET
    assert req.host == "api.github.com"
    assert req.protocol == Protocol.HTTPS
    assert req.body == ""
    assert req.headers == {}
    assert req.pathname == "/v1/users"
    assert req.path == "/v1/users?a=b&q=1&q=2"


def test_from_url():
    test_url = "https://api.github.com/v1/repos?id=1&q=v1&q=v2"
    req = RequestBuilder.from_url(test_url)
    assert req.method == HttpMethod.GET
    assert req.host == "api.github.com"
    assert req.protocol == "https"
    assert req.path == "/v1/repos?id=1&q=v1&q=v2"
    assert req.pathname == "/v1/repos"
    assert req.query == {"id": "1", "q": ["v1", "v2"]}


def test_from_url_without_path():
    test_url = "https://api.github.com"
    req = RequestBuilder.from_url(test_url)
    assert req.path == "/"
    assert req.pathname == "/"


def test_from_url_with_root_path():
    test_url = "https://api.github.com/"
    req = RequestBuilder.from_url(test_url)
    assert req.path == "/"
    assert req.pathname == "/"


def test_from_json():
    with open(SAMPLE_JSON, "r", encoding="utf-8") as f:
        exchange = HttpExchangeReader.from_json(f.read())
        assert exchange.request.timestamp == isoparse("2018-11-13T20:20:39+02:00")
        assert exchange.response.timestamp == isoparse("2020-01-31T13:34:15")


def test_invalid_timestamp_in_json():
    with open(SAMPLE_JSON, "r", encoding="utf-8") as f:
        json_string = f.read().replace("2018-11-13T20:20:39+02:00", "INVALID_STRING")
        try:
            HttpExchangeReader.from_json(json_string)
            raise AssertionError("No exception raised from invalid timestamp")
        except ValueError as e:
            assert str(e) == "Invalid isoformat string: INVALID_STRING"


def test_from_jsonl():
    with open(SAMPLE_JSONL, "r", encoding="utf-8") as f:
        exchanges = list(HttpExchangeReader.from_jsonl(f))
        validate_sample_exchanges(exchanges)


def validate_sample_exchanges(exchanges):
    assert len(exchanges) == 3
    assert exchanges[0].request.protocol == Protocol.HTTP
    assert exchanges[1].request.protocol == Protocol.HTTPS

    for exchange in exchanges[0:2]:
        assert exchange.request.path == "/user/repos?q=v"
        assert exchange.request.pathname == "/user/repos"
        assert exchange.request.query == {"q": "v"}

    assert exchanges[2].request.path == "/user/repos"
    assert exchanges[2].request.pathname == "/user/repos"
    assert exchanges[2].request.query == {}


def test_writing_json():
    buffer = StringIO()
    writer = HttpExchangeWriter(buffer)

    original_exchanges = []
    with open(SAMPLE_JSONL, "r", encoding="utf-8") as f:
        for exchange in HttpExchangeReader.from_jsonl(f):
            original_exchanges.append(exchange)
            writer.write(exchange)

    buffer.seek(0)
    schema = read_schema()
    for line in buffer:
        jsonschema.validate(instance=json.loads(line), schema=schema)

    buffer.seek(0)
    exchanges = list(HttpExchangeReader.from_jsonl(buffer))
    validate_sample_exchanges(exchanges)
    assert original_exchanges == exchanges


def test_example_from_readme():
    request = RequestBuilder.from_dict(
        {
            "host": "api.github.com",
            "protocol": "https",
            "method": "get",
            "pathname": "/v1/users",
            "query": {"a": "b", "q": ["1", "2"]},
        }
    )

    response = ResponseBuilder.from_dict(
        {
            "statusCode": 200,
            "headers": {"content-type": "text/plain"},
            "body": "(response body string)",
        }
    )

    exchange = HttpExchange(request=request, response=response)

    output_file = StringIO()
    writer = HttpExchangeWriter(output_file)
    writer.write(exchange)

    input_file = output_file
    input_file.seek(0)

    for exchange in HttpExchangeReader.from_jsonl(input_file):
        assert exchange.request.method == HttpMethod.GET
        assert exchange.request.protocol == Protocol.HTTPS
        assert exchange.response.statusCode == 200
