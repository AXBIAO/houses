from __future__ import annotations

import uuid


def _register(client, **overrides):
    body = {"email": f"u{uuid.uuid4().hex[:8]}@example.com", "username": "租客", "password": "Passw0rd!"}
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_site(client):
    assert client.get("/api/health").json()["status"] == "ok"
    site = client.get("/api/site").json()
    assert site["license"] == "AGPL-3.0"


def test_migrations_applied_and_superadmin_bootstrapped(sql):
    assert sql("SELECT version FROM app_schema_migrations ORDER BY version") == [(1,), (2,), (3,), (4,), (5,), (6,)]
    rows = sql("SELECT role FROM users WHERE email = 'root@example.com'")
    assert rows == [("superadmin",)]


def test_register_then_me(client):
    res = _register(client)
    assert res.status_code == 201
    token = res.json()["token"]
    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "user"


def test_register_with_phone(client):
    res = _register(client, email=None, phone="13800000001")
    assert res.status_code == 201
    assert res.json()["user"]["phone"] == "13800000001"


def test_register_rejects_duplicates_case_insensitive(client):
    email = f"Dup{uuid.uuid4().hex[:6]}@Example.com"
    assert _register(client, email=email).status_code == 201
    assert _register(client, email=email.lower()).status_code == 409


def test_register_validation(client):
    assert _register(client, password="short").status_code == 422
    assert _register(client, email=None, phone="12345").status_code == 422
    assert _register(client, email=None, phone=None).status_code == 422


def test_login_success_and_failure(client):
    email = f"login{uuid.uuid4().hex[:6]}@example.com"
    _register(client, email=email)
    assert client.post("/api/auth/login", json={"account": email, "password": "wrong-pass"}).status_code == 401
    ok = client.post("/api/auth/login", json={"account": email.upper(), "password": "Passw0rd!"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me", headers=_auth(ok.json()["token"])).status_code == 200


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=_auth("not-a-jwt")).status_code == 401


def test_disabled_account_token_rejected_immediately(client, sql):
    res = _register(client)
    token, user_id = res.json()["token"], res.json()["user"]["id"]
    sql("UPDATE users SET disabled = TRUE WHERE id = %s", (user_id,))
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401


def test_password_version_bump_revokes_old_tokens(client, sql):
    res = _register(client)
    token, user_id = res.json()["token"], res.json()["user"]["id"]
    sql("UPDATE users SET pwd_ver = pwd_ver + 1 WHERE id = %s", (user_id,))
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401


def test_login_lockout_after_repeated_failures(client):
    email = f"lock{uuid.uuid4().hex[:6]}@example.com"
    _register(client, email=email)
    for _ in range(10):
        assert client.post("/api/auth/login", json={"account": email, "password": "bad"}).status_code == 401
    locked = client.post("/api/auth/login", json={"account": email, "password": "Passw0rd!"})
    assert locked.status_code == 429
