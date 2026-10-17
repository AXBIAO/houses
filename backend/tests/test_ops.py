"""上线相关：生产自检、安全头、健康检查、站点地图、注册限流。"""
from __future__ import annotations

import os
import uuid

import pytest
import redis

from backend.app.core.config import Settings
from backend.app.core.production_checks import assert_production_ready, production_problems

GOOD_PRODUCTION = dict(
    environment="production", source_code_url="https://github.com/example/houses", public_base_url="https://houses.example.com",
    cors_allowed_origins="https://houses.example.com", bootstrap_admin_password="", postgres_password="a-long-db-password",
    redis_password="redis-secret",
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**GOOD_PRODUCTION, **overrides})


def test_development_skips_production_checks():
    assert production_problems(_settings(environment="development", source_code_url="")) == []


def test_good_production_config_passes():
    assert production_problems(_settings()) == []
    assert_production_ready(_settings())


@pytest.mark.parametrize(("override", "fragment"), [
    ({"source_code_url": ""}, "AGPL-3.0"),
    ({"public_base_url": "http://houses.example.com"}, "PUBLIC_BASE_URL"),
    ({"public_base_url": "https://localhost"}, "PUBLIC_BASE_URL"),
    ({"cors_allowed_origins": "https://houses.example.com,http://localhost:5180"}, "CORS"),
    ({"bootstrap_admin_password": "short"}, "BOOTSTRAP_ADMIN_PASSWORD"),
    ({"postgres_password": "pw"}, "POSTGRES_PASSWORD"),
    ({"redis_password": ""}, "REDIS_PASSWORD"),
])
def test_bad_production_config_is_rejected(override, fragment):
    problems = production_problems(_settings(**override))
    assert len(problems) == 1 and fragment in problems[0]
    with pytest.raises(RuntimeError, match=fragment):
        assert_production_ready(_settings(**override))


def test_security_headers_and_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["database"] is True
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert "geolocation=(self)" in res.headers["permissions-policy"]
    assert "strict-transport-security" not in res.headers  # 仅生产环境开启
    assert client.get("/docs").status_code == 200  # 开发环境保留接口文档


def test_sitemap_lists_public_listings_only(client, sql):
    landlord = sql("INSERT INTO landlords (name) VALUES ('地图房东') RETURNING id")[0][0]
    estate = sql("INSERT INTO estates (landlord_id, name, city, district, lat, lng) VALUES (%s, '地图小区', '成都', '地图区', 30, 104) RETURNING id",
                 (landlord,))[0][0]
    insert = ("INSERT INTO listings (landlord_id, estate_id, rent_type, title, area, price_month, status, published_at) "
              "VALUES (%s, %s, 'long', %s, 30, 1000, %s, CASE WHEN %s = 'published' THEN now() END) RETURNING id")
    public = sql(insert, (landlord, estate, "公开", "published", "published"))[0][0]
    draft = sql(insert, (landlord, estate, "草稿", "draft", "draft"))[0][0]
    res = client.get("/sitemap.xml")
    assert res.status_code == 200 and res.headers["content-type"].startswith("application/xml")
    assert f"/listings/{public}</loc>" in res.text and f"/listings/{draft}</loc>" not in res.text
    assert "<loc>http://127.0.0.1:5180/about</loc>" in res.text
    sql("UPDATE landlords SET status = 'disabled' WHERE id = %s", (landlord,))


def test_register_rate_limit(client):
    r = redis.Redis(host="localhost", port=int(os.environ["REDIS_PORT"]), db=15)
    r.set("houses:register:testclient", 10)
    try:
        res = client.post("/api/auth/register", json={"email": f"rl{uuid.uuid4().hex[:6]}@example.com", "username": "x", "password": "Passw0rd!"})
        assert res.status_code == 429
    finally:
        r.delete("houses:register:testclient")
