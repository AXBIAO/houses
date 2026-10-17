"""生产环境启动自检：配置不合格时拒绝启动，比上线后才发现问题更安全。"""
from __future__ import annotations

from urllib.parse import urlparse

from backend.app.core.config import Settings

MIN_SECRET_PASSWORD = 12
LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")


def production_problems(s: Settings) -> list[str]:
    if s.environment.lower() != "production":
        return []
    problems: list[str] = []
    if not s.source_code_url.startswith(("https://", "http://")):
        problems.append("AGPL-3.0 要求向网络用户提供源码：请设置 SOURCE_CODE_URL 为公开仓库地址")
    base = urlparse(s.public_base_url)
    if base.scheme != "https" or base.hostname in LOCAL_HOSTS:
        problems.append("PUBLIC_BASE_URL 需为对外的 https 地址（通知邮件里的链接会用到）")
    if any((urlparse(o).hostname or "") in LOCAL_HOSTS for o in s.cors_origins()):
        problems.append("CORS_ALLOWED_ORIGINS 不应包含本机地址")
    if s.bootstrap_admin_password and len(s.bootstrap_admin_password) < MIN_SECRET_PASSWORD:
        problems.append(f"BOOTSTRAP_ADMIN_PASSWORD 至少 {MIN_SECRET_PASSWORD} 位；超管创建后可清空该变量")
    if len(s.postgres_password) < MIN_SECRET_PASSWORD:
        problems.append(f"POSTGRES_PASSWORD 至少 {MIN_SECRET_PASSWORD} 位")
    if not s.redis_password:
        problems.append("生产环境请为 Redis 设置 REDIS_PASSWORD")
    return problems


def assert_production_ready(s: Settings) -> None:
    problems = production_problems(s)
    if problems:
        raise RuntimeError("生产环境配置不合格：\n- " + "\n- ".join(problems))
