"""测试使用同一 PostgreSQL 容器里的独立库 houses_test，每次会话重建；Redis 用 db 15 并在开始时清空。"""
from __future__ import annotations

import os
import secrets
import tempfile

import psycopg
import pytest

TEST_DB = "houses_test"
os.environ.update({
    "POSTGRES_HOST": os.environ.get("TEST_POSTGRES_HOST", "localhost"),
    "POSTGRES_PORT": os.environ.get("TEST_POSTGRES_PORT", "25432"),
    "POSTGRES_USER": "houses",
    "POSTGRES_PASSWORD": os.environ.get("TEST_POSTGRES_PASSWORD", "houses_dev_pw"),
    "POSTGRES_DATABASE": TEST_DB,
    "POSTGRES_SSLMODE": "disable",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": os.environ.get("TEST_REDIS_PORT", "16379"),
    "REDIS_DB": "15",
    "JWT_SECRET_KEY": secrets.token_hex(32),
    "BOOTSTRAP_ADMIN_EMAIL": "root@example.com",
    "BOOTSTRAP_ADMIN_PASSWORD": "Root@123456",
    "UPLOAD_DIR": tempfile.mkdtemp(prefix="houses-uploads-"),
    "SCHEDULER_ENABLED": "false",
})


def _admin_conninfo() -> str:
    return (f"host={os.environ['POSTGRES_HOST']} port={os.environ['POSTGRES_PORT']} user=houses "
            f"password={os.environ['POSTGRES_PASSWORD']} dbname=houses")


@pytest.fixture(scope="session", autouse=True)
def fresh_database() -> None:
    with psycopg.connect(_admin_conninfo(), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB}")
    import redis
    redis.Redis(host="localhost", port=int(os.environ["REDIS_PORT"]), db=15).flushdb()


@pytest.fixture(scope="session")
def client(fresh_database):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sql():
    """直接执行 SQL，用于构造测试前置状态。"""
    def run(query: str, params: tuple = ()):
        info = _admin_conninfo().replace("dbname=houses", f"dbname={TEST_DB}")
        with psycopg.connect(info, autocommit=True) as conn:
            cur = conn.execute(query, params)
            return cur.fetchall() if cur.description else None
    return run


@pytest.fixture(autouse=True)
def reset_register_limit():
    """测试会从同一 IP 注册大量账号；注册限流本身在 test_ops 里单独验证。"""
    import redis

    client = redis.Redis(host="localhost", port=int(os.environ["REDIS_PORT"]), db=15)
    for key in client.scan_iter("houses:register:*"):
        client.delete(key)
