# Modified for Houses (based on AIGCNEWS, AGPL-3.0): removed membership/MCP/feed tokens,
# added platform roles (superadmin / platform_admin).
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# 平台角色（存于 users.role）。房东/房东员工是租户内角色，见 tenant_members。
ROLE_USER = "user"
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_SUPERADMIN = "superadmin"
PLATFORM_ROLES = frozenset({ROLE_PLATFORM_ADMIN, ROLE_SUPERADMIN})


class UserIdentityReader(Protocol):
    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# Password hashing（bcrypt 官方库）
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)

KNOWN_INSECURE_JWT_SECRETS: frozenset[str] = frozenset(
    {"change-me-in-production", "change-me-in-production-use-a-long-random-string"}
)
MIN_JWT_SECRET_LENGTH = 32


def validate_jwt_secret(secret: str) -> None:
    """Fail fast when the JWT signing secret is missing, leaked, or too weak."""
    if not secret or secret in KNOWN_INSECURE_JWT_SECRETS:
        raise RuntimeError("JWT_SECRET_KEY 未配置或仍为公开的示例值，拒绝启动。请用 `openssl rand -hex 32` 生成并写入 .env。")
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(f"JWT_SECRET_KEY 长度不足 {MIN_JWT_SECRET_LENGTH} 字符，拒绝启动。")


def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        logger.warning("[Auth] JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------


def get_user_identity_repository(request: Request) -> UserIdentityReader | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    return getattr(request.app.state, "users", None)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


async def RequireUser(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    repository: UserIdentityReader | None = Depends(get_user_identity_repository),
) -> dict[str, Any]:
    """要求有效 Bearer JWT，并以库内状态为准：账号禁用/删除立即生效，改密（pwd_ver 递增）即撤销旧 token，
    角色一律取库内值（token 内角色只是签发快照）。"""
    if credentials is None:
        raise _unauthorized("缺少 Authorization 头")
    payload = decode_access_token(credentials.credentials)
    user_id = extract_user_id(payload)
    if user_id is None:
        raise _unauthorized("用户身份无效")
    if repository is None:
        raise RuntimeError("User repository is not configured")
    record = await asyncio.to_thread(repository.get_user_by_id, user_id)
    if record is None or record.get("disabled"):
        raise _unauthorized("账号不存在或已被禁用")
    if payload.get("pwd_ver") != record.get("pwd_ver"):
        raise _unauthorized("登录状态已失效，请重新登录")
    identity = dict(payload)
    identity["user_id"] = user_id
    identity["role"] = record.get("role") or ROLE_USER
    return identity


async def OptionalUser(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    repository: UserIdentityReader | None = Depends(get_user_identity_repository),
) -> dict[str, Any] | None:
    """可选登录态：缺失或无效 token 都按匿名处理。"""
    if credentials is None:
        return None
    try:
        return await RequireUser(credentials=credentials, repository=repository)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        return None


def extract_user_id(identity: Mapping[str, Any] | None) -> int | None:
    if not isinstance(identity, Mapping):
        return None
    raw = identity.get("user_id") or identity.get("id") or identity.get("sub")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


async def RequirePlatformAdmin(user: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    """平台管理员或超级管理员。"""
    if user.get("role") not in PLATFORM_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要平台管理员")
    return user


async def RequireSuperAdmin(user: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    if user.get("role") != ROLE_SUPERADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要超级管理员")
    return user
