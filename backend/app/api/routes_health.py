"""健康检查与站点元信息。"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request, Response, status

from backend.app.core.config import settings
from backend.app.core.postgres_database import postgres_database

router = APIRouter(prefix="/api", tags=["site"])


def _db_ok() -> bool:
    try:
        with postgres_database.transaction() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@router.get("/health")
async def health(request: Request, response: Response) -> dict[str, Any]:
    """容器健康检查：数据库不可用时返回 503，Redis 只作为附加信息（缺失时服务降级运行）。"""
    database = await asyncio.to_thread(_db_ok)
    if not database:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if database else "degraded", "app": settings.app_name, "database": database,
            "redis": getattr(request.app.state, "redis", None) is not None}


@router.get("/site")
async def site() -> dict[str, Any]:
    """前端页脚使用：AGPL-3.0 要求向网络用户提供源码链接。"""
    return {"name": settings.app_name, "license": "AGPL-3.0", "sourceCodeUrl": settings.source_code_url}
