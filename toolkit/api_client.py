from __future__ import annotations
import requests


class ApiAssertionError(AssertionError):
    pass


class ApiResponse:
    def __init__(self, resp: requests.Response, elapsed_ms: float):
        self.resp = resp
        self.elapsed_ms = elapsed_ms

    def assert_status(self, expected: int) -> "ApiResponse":
        if self.resp.status_code != expected:
            raise ApiAssertionError(
                f"Expected status {expected}, got {self.resp.status_code}")
        return self

    def assert_under_ms(self, budget_ms: int) -> "ApiResponse":
        if self.elapsed_ms > budget_ms:
            raise ApiAssertionError(
                f"Response took {self.elapsed_ms:.0f}ms > budget {budget_ms}ms")
        return self

    def assert_business_code(self, code: str) -> "ApiResponse":
        actual = self.resp.headers.get("x-business-code")
        if actual != code:
            raise ApiAssertionError(
                f"Expected business code header {code}, got {actual}")
        return self

    def assert_schema(self, schema: dict) -> "ApiResponse":
        body = self.resp.json()
        for key, typ in schema.items():
            if key not in body:
                raise ApiAssertionError(f"Missing required field '{key}'")
            if not isinstance(body[key], typ):
                raise ApiAssertionError(
                    f"Field '{key}' expected {typ.__name__}, "
                    f"got {type(body[key]).__name__}")
        return self


class ApiClient:
    def __init__(self, base_url: str, default_headers: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

    def request(self, method: str, path: str, **kwargs) -> ApiResponse:
        url = self.base_url + path
        resp = self.session.request(method, url, **kwargs)
        return ApiResponse(resp, resp.elapsed.total_seconds() * 1000)

    def get(self, path: str, **kwargs) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ApiResponse:
        return self.request("POST", path, **kwargs)
