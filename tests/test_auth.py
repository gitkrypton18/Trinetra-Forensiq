"""Authentication tests: register, login, token guard, roles, throttle."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import api


def _register(client: TestClient, username: str, password: str = "pass1234"):
    return client.post("/auth/register",
                       json={"username": username, "password": password})


def test_register_first_user_becomes_admin(client):
    """The fixture's own first user is the admin bootstrap."""
    me = client.get("/auth/me").json()
    assert me["user"]["role"] == "admin"


def test_register_second_user_is_officer(client):
    _register(client, "alice")
    assert _register(client, "bob").json()["user"]["role"] == "officer"


def test_register_duplicate_username(client):
    _register(client, "alice")
    assert _register(client, "alice").status_code == 409


def test_register_weak_password_rejected(client):
    assert _register(client, "weak", password="123").status_code == 400


def test_login_roundtrip(client):
    _register(client, "alice")
    r = client.post("/auth/login", json={"username": "alice",
                                         "password": "pass1234"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "alice"
    me = client.get("/auth/me",
                    headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"


def test_login_wrong_password(client):
    _register(client, "alice")
    r = client.post("/auth/login", json={"username": "alice",
                                         "password": "wrongpass1"})
    assert r.status_code == 401


def test_login_throttle_locks_account(client):
    _register(client, "alice")
    for _ in range(8):
        client.post("/auth/login", json={"username": "alice",
                                         "password": "wrongpass1"})
    r = client.post("/auth/login", json={"username": "alice",
                                         "password": "pass1234"})
    assert r.status_code == 429


def test_protected_endpoints_reject_anonymous(client):
    anon = TestClient(api.app)  # no default Authorization header
    assert anon.get("/summary").status_code == 401
    assert anon.get("/accounts").status_code == 401
    assert anon.get("/scoring/alerts").status_code == 401
    assert anon.get("/ingest/status").status_code == 401
    assert anon.post("/ingest", json={"folder": "C:/x"}).status_code == 401
    assert anon.get("/graph/money").status_code == 401
    assert anon.get("/search?q=1").status_code == 401


def test_garbage_token_rejected(client):
    r = client.get("/summary",
                   headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_tampered_token_rejected(client):
    _register(client, "alice")
    tok = client.post("/auth/login", json={"username": "alice",
                                           "password": "pass1234"}).json()
    parts = tok["access_token"].split(".")
    bad = parts[0] + "." + parts[1] + "." + "0" * 64
    r = client.get("/summary", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_health_and_root_are_public(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_delete_ingest_requires_admin(client, fixtures_dir):
    """Officers may not wipe the loaded bundle."""
    _register(client, "alice")
    _register(client, "bob")
    tok = client.post("/auth/login", json={"username": "bob",
                                           "password": "pass1234"}).json()
    officer = {"Authorization": f"Bearer {tok['access_token']}"}

    admin = client.post("/ingest", json={"folder": str(fixtures_dir)})
    assert admin.status_code == 200

    r = client.delete("/ingest", headers=officer)
    assert r.status_code == 403
    # admin can still wipe
    assert client.delete("/ingest").status_code == 200


def test_signup_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ALLOW_SIGNUP", "0")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    api._state.clear()
    with TestClient(api.app) as c:
        r = c.post("/auth/register", json={"username": "nobody",
                                           "password": "pass1234"})
        assert r.status_code == 403
    api._state.clear()
