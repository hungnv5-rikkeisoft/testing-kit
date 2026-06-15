import pytest
from toolkit.api_client import ApiClient, ApiAssertionError


def test_status_and_schema_and_timing(httpserver):
    httpserver.expect_request("/ok").respond_with_json(
        {"id": 1, "name": "x"}, status=200)
    client = ApiClient(base_url=httpserver.url_for(""))
    resp = client.get("/ok")
    resp.assert_status(200).assert_schema({"id": int, "name": str}).assert_under_ms(5000)


def test_wrong_status_raises(httpserver):
    httpserver.expect_request("/bad").respond_with_json({}, status=400)
    client = ApiClient(base_url=httpserver.url_for(""))
    with pytest.raises(ApiAssertionError):
        client.get("/bad").assert_status(200)


def test_business_error_header(httpserver):
    # strategy 1.3.3: business error => HTTP 200 + a business code header
    httpserver.expect_request("/biz").respond_with_json(
        {}, status=200, headers={"x-business-code": "42"})
    client = ApiClient(base_url=httpserver.url_for(""))
    client.get("/biz").assert_status(200).assert_business_code("42")


def test_schema_mismatch_raises(httpserver):
    httpserver.expect_request("/s").respond_with_json({"id": "not-int"}, status=200)
    client = ApiClient(base_url=httpserver.url_for(""))
    with pytest.raises(ApiAssertionError):
        client.get("/s").assert_schema({"id": int})
