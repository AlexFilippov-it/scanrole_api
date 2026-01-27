from fastapi.testclient import TestClient

import auth
import config
import main


def _set_settings(monkeypatch):
    settings = config.Settings(
        wp_introspect_url="http://wp.local/introspect",
        wp_introspect_secret="secret",
        db_host="localhost",
        db_name="db",
        db_user="user",
        db_pass="pass",
        role_table="jobspy_normalized_jobs",
        api_base_url="*",
        log_level="info",
    )
    monkeypatch.setattr(main, "settings", settings)
    return settings


def test_meta_roles_missing_token(monkeypatch):
    _set_settings(monkeypatch)
    client = TestClient(main.app)

    resp = client.get("/api/v1/meta/roles")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_meta_roles_inactive_token(monkeypatch):
    _set_settings(monkeypatch)

    async def fake_introspect(_token: str):
        return {"active": False}

    monkeypatch.setattr(auth, "introspect_token", fake_introspect)

    client = TestClient(main.app)
    resp = client.get("/api/v1/meta/roles", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_meta_roles_missing_scope(monkeypatch):
    _set_settings(monkeypatch)

    async def fake_introspect(_token: str):
        return {"active": True, "scopes": []}

    monkeypatch.setattr(auth, "introspect_token", fake_introspect)

    client = TestClient(main.app)
    resp = client.get("/api/v1/meta/roles", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_meta_roles_success(monkeypatch):
    _set_settings(monkeypatch)

    async def fake_introspect(_token: str):
        return {"active": True, "scopes": ["read:role_explorer"]}

    monkeypatch.setattr(auth, "introspect_token", fake_introspect)
    monkeypatch.setattr(main, "get_roles", lambda _table: ["Engineer"])

    client = TestClient(main.app)
    resp = client.get("/api/v1/meta/roles", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json()["items"] == ["Engineer"]
