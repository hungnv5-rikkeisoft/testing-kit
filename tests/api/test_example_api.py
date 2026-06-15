import pytest
from toolkit.api_client import ApiClient


@pytest.mark.api
def test_endpoint_returns_200_and_schema_within_budget(httpserver):
    httpserver.expect_request("/users/1").respond_with_json(
        {"id": 1, "name": "Alice"}, status=200)
    client = ApiClient(base_url=httpserver.url_for(""))
    (client.get("/users/1")
        .assert_status(200)
        .assert_schema({"id": int, "name": str})
        .assert_under_ms(600))  # strategy: API < 600ms
