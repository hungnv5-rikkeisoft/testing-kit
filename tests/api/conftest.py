"""API-layer fixtures: bind httpserver to 127.0.0.1 to avoid the Windows
IPv6 localhost TCP connect delay (~2 s) that would blow the 600 ms budget."""
import pytest


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 0)
