"""后台系统设置（大模型 / 邮件）、修改密码、robots.txt。"""
from __future__ import annotations

import uuid

import httpx
import pytest

from backend.app.core import llm as llm_module, secret_box

REAL_ASYNC_CLIENT = httpx.AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def root(client):
    return _auth(client.post("/api/auth/login", json={"account": "root@example.com", "password": "Root@123456"}).json()["token"])


@pytest.fixture(autouse=True)
def reset_settings(client, root):
    yield
    for key in ("llm", "smtp"):
        client.delete(f"/api/admin/settings/{key}", headers=root)


def _user(client):
    email = f"acct{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/auth/register", json={"email": email, "username": "改密", "password": "OldPassw0rd!"})
    return email, _auth(res.json()["token"])


def _mock_llm(monkeypatch, content: str, status: int = 200):
    response = (httpx.Response(status, json={"choices": [{"message": {"content": content}}]}) if status == 200
                else httpx.Response(status, text="invalid api key"))
    monkeypatch.setattr(llm_module.httpx, "AsyncClient",
                        lambda **kw: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(lambda req: response), **kw))


def test_settings_require_superadmin(client):
    _, h = _user(client)
    assert client.get("/api/admin/settings").status_code == 401
    assert client.get("/api/admin/settings", headers=h).status_code == 403
    assert client.put("/api/admin/settings/llm", headers=h, json={}).status_code == 403


def test_llm_settings_saved_encrypted_and_masked(client, root, sql):
    initial = client.get("/api/admin/settings", headers=root).json()
    assert initial["llm"]["source"] == "none" and initial["llm"]["enabled"] is False

    body = {"baseUrl": "https://api.deepseek.com/v1/", "model": "deepseek-chat", "apiKey": "sk-test-abcdef1234", "timeout": 20}
    saved = client.put("/api/admin/settings/llm", headers=root, json=body).json()
    assert saved == {"source": "db", "enabled": True, "baseUrl": "https://api.deepseek.com/v1", "model": "deepseek-chat",
                     "timeout": 20.0, "apiKeySet": True, "apiKeyTail": "1234"}
    stored = sql("SELECT value->>'apiKey' FROM app_settings WHERE key = 'llm'")[0][0]
    assert "sk-test" not in stored and secret_box.decrypt(stored) == "sk-test-abcdef1234"
    assert "sk-test" not in client.get("/api/admin/settings", headers=root).text

    kept = client.put("/api/admin/settings/llm", headers=root, json={**body, "apiKey": None, "model": "deepseek-v3"}).json()
    assert kept["apiKeyTail"] == "1234" and kept["model"] == "deepseek-v3"
    cleared = client.put("/api/admin/settings/llm", headers=root, json={**body, "apiKey": ""}).json()
    assert cleared["apiKeySet"] is False and cleared["enabled"] is False
    assert client.put("/api/admin/settings/llm", headers=root, json={**body, "baseUrl": "ftp://x"}).status_code == 422


def test_llm_probe_and_ai_search_use_saved_config(client, root, monkeypatch):
    client.put("/api/admin/settings/llm", headers=root, json={"baseUrl": "https://llm.example/v1", "model": "m", "apiKey": "sk-123456789"})
    _mock_llm(monkeypatch, '{"rentType": "short", "maxPrice": 300}')
    probe = client.post("/api/admin/settings/llm/test", headers=root, json={}).json()
    assert probe["ok"] is True and probe["filters"] == {"type": "short", "maxPrice": "300"}
    ai = client.post("/api/ai/search", json={"query": "随便看看"}).json()
    assert ai["source"] == "llm" and ai["llmEnabled"] is True and ai["filters"]["type"] == "short"

    _mock_llm(monkeypatch, "", status=401)
    failed = client.post("/api/admin/settings/llm/test", headers=root, json={}).json()
    assert failed["ok"] is False and "401" in failed["message"]
    assert client.post("/api/ai/search", json={"query": "两室"}).json()["source"] == "rules"  # 失败回退规则


def test_smtp_settings_and_test_mail(client, root, monkeypatch):
    sent = []

    async def fake_send(message, **kwargs):
        sent.append((message["To"], kwargs["hostname"], kwargs["use_tls"], kwargs["password"]))

    monkeypatch.setattr("backend.app.core.mailer.aiosmtplib.send", fake_send)
    assert client.post("/api/admin/settings/smtp/test", headers=root, json={"to": "a@example.com"}).json()["ok"] is False
    saved = client.put("/api/admin/settings/smtp", headers=root, json={
        "host": "smtp.example.com", "port": 465, "user": "noreply@example.com", "password": "mail-secret-9876",
        "sender": "房子 Houses <noreply@example.com>", "useTls": True}).json()
    assert saved["enabled"] and saved["passwordTail"] == "9876" and "mail-secret" not in str(saved)
    res = client.post("/api/admin/settings/smtp/test", headers=root, json={"to": "a@example.com"}).json()
    assert res == {"ok": True, "message": "已发送到 a@example.com"}
    assert sent == [("a@example.com", "smtp.example.com", True, "mail-secret-9876")]

    _, h = _user(client)
    assert client.get("/api/subscriptions", headers=h).json()["emailAvailable"] is True

    async def failing(message, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("backend.app.core.mailer.aiosmtplib.send", failing)
    bad = client.post("/api/admin/settings/smtp/test", headers=root, json={"to": "a@example.com"}).json()
    assert bad["ok"] is False and "connection refused" in bad["message"]


def test_reset_falls_back_to_env(client, root):
    client.put("/api/admin/settings/llm", headers=root, json={"baseUrl": "https://x.example", "model": "m", "apiKey": "sk-123456789"})
    assert client.delete("/api/admin/settings/llm", headers=root).json()["llm"]["source"] == "none"


def test_secret_box_rejects_foreign_ciphertext(monkeypatch):
    token = secret_box.encrypt("hello")
    monkeypatch.setattr(secret_box.settings, "JWT_SECRET_KEY", "another-secret-" * 4)
    assert secret_box.decrypt(token) is None
    assert secret_box.tail("abcdefgh") == "efgh" and secret_box.tail("short") == "****" and secret_box.tail(None) is None


def test_change_password(client):
    email, old = _user(client)
    assert client.post("/api/auth/password", headers=old, json={"oldPassword": "wrong", "newPassword": "NewPassw0rd!"}).status_code == 400
    assert client.post("/api/auth/password", headers=old, json={"oldPassword": "OldPassw0rd!", "newPassword": "OldPassw0rd!"}).status_code == 400
    assert client.post("/api/auth/password", headers=old, json={"oldPassword": "OldPassw0rd!", "newPassword": "short"}).status_code == 422
    res = client.post("/api/auth/password", headers=old, json={"oldPassword": "OldPassw0rd!", "newPassword": "NewPassw0rd!"})
    assert res.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401  # 旧令牌立即失效
    assert client.get("/api/auth/me", headers=_auth(res.json()["token"])).status_code == 200
    assert client.post("/api/auth/login", json={"account": email, "password": "NewPassw0rd!"}).status_code == 200
    assert client.post("/api/auth/password", json={"oldPassword": "x", "newPassword": "NewPassw0rd!"}).status_code == 401


def test_robots_txt(client):
    res = client.get("/robots.txt")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/plain")
    assert "Disallow: /landlord" in res.text and "Sitemap: http://127.0.0.1:5180/sitemap.xml" in res.text
