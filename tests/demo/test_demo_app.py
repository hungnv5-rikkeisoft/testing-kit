import pytest
from demo.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _login(client, email, password):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=False)


def test_screen_requires_login(client):
    resp = client.get("/")
    assert resp.status_code in (302, 401)


def test_login_success_then_screen(client):
    assert _login(client, "a@example.com", "a").status_code in (302, 200)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Usage" in resp.data
    assert b"Prefecture" in resp.data


def test_login_failure(client):
    resp = _login(client, "a@example.com", "wrong")
    assert resp.status_code == 401


def test_guest_no_permission(client):
    _login(client, "noperm@example.com", "n")
    resp = client.get("/")
    assert resp.status_code == 403


def test_municipalities_cascade(client):
    _login(client, "a@example.com", "a")
    resp = client.get("/api/municipalities?prefecture=13")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["municipalities"], list) and data["municipalities"]


def test_basic_info_validation_empty(client):
    _login(client, "a@example.com", "a")
    resp = client.post("/api/basic-info", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_basic_info_valid(client):
    _login(client, "a@example.com", "a")
    resp = client.post("/api/basic-info", json={
        "usage": "Residential", "prefecture": "13", "municipality": "Chiyoda"})
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True


def test_xss_echo_is_escaped(client):
    _login(client, "a@example.com", "a")
    payload = "<script>alert('x')</script>"
    resp = client.post("/api/basic-info", json={
        "usage": "Residential", "prefecture": "13",
        "municipality": payload})
    assert b"<script>" not in resp.data


def test_user_b_cannot_read_user_a(client):
    _login(client, "a@example.com", "a")
    client.post("/api/basic-info", json={
        "usage": "Residential", "prefecture": "13", "municipality": "Chiyoda"})
    client.get("/logout")
    _login(client, "b@example.com", "b")
    resp = client.get("/api/basic-info?owner=a@example.com")
    assert resp.status_code == 403
