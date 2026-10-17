"""注册、登录、当前用户。"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, model_validator

from backend.app.core.auth import RequireUser, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

PHONE_RE = re.compile(r"^1\d{10}$")
LOGIN_FAIL_LIMIT = 10
LOGIN_FAIL_WINDOW_SECONDS = 15 * 60


class RegisterBody(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def _account_required(self) -> "RegisterBody":
        if not self.email and not self.phone:
            raise ValueError("邮箱和手机号至少填一个")
        if self.phone and not PHONE_RE.fullmatch(self.phone):
            raise ValueError("手机号格式不正确")
        return self


class PasswordBody(BaseModel):
    oldPassword: str = Field(min_length=1, max_length=72)
    newPassword: str = Field(min_length=8, max_length=72)


class LoginBody(BaseModel):
    account: str = Field(min_length=3, max_length=120, description="邮箱或手机号")
    password: str = Field(min_length=1, max_length=72)


def _users(request: Request):
    return request.app.state.users


def _public(user: dict[str, Any], membership: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {k: user.get(k) for k in ("id", "email", "phone", "username", "role", "created_at")}
    out["landlord"] = (
        {"id": membership["landlord_id"], "name": membership["name"], "role": membership["role"],
         "active": membership["status"] == "active"}
        if membership else None
    )
    return out


async def _membership(request: Request, user_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(request.app.state.landlords.membership_for_user, user_id)


def _token_for(user: dict[str, Any]) -> str:
    return create_access_token({"sub": str(user["id"]), "pwd_ver": user["pwd_ver"]})


async def _guard_login(request: Request, account: str) -> str | None:
    """同一账号+IP 15 分钟内失败 10 次即锁定；没有 Redis 时不限流（仅本地开发）。"""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return None
    ip = request.client.host if request.client else "unknown"
    key = f"houses:login-fail:{account.lower()}:{ip}"
    if int(await redis.get(key) or 0) >= LOGIN_FAIL_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "登录失败次数过多，请 15 分钟后再试")
    return key


async def _record_failure(request: Request, key: str | None) -> None:
    redis = getattr(request.app.state, "redis", None)
    if redis is None or key is None:
        return
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, LOGIN_FAIL_WINDOW_SECONDS)


REGISTER_LIMIT = 10
REGISTER_WINDOW_SECONDS = 60 * 60


async def _guard_register(request: Request) -> None:
    """同一 IP 每小时最多注册 10 个账号，防止批量注册。"""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return
    ip = request.client.host if request.client else "unknown"
    key = f"houses:register:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, REGISTER_WINDOW_SECONDS)
    if count > REGISTER_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "注册太频繁，请稍后再试")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterBody, request: Request) -> dict[str, Any]:
    await _guard_register(request)
    users = _users(request)
    email = str(body.email) if body.email else None
    if await asyncio.to_thread(users.exists, email=email, phone=body.phone):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱或手机号已注册")
    user = await asyncio.to_thread(users.create_user, email=email, phone=body.phone,
                                   username=body.username.strip(), password_hash=hash_password(body.password))
    return {"token": _token_for(user), "user": _public(user)}


@router.post("/login")
async def login(body: LoginBody, request: Request) -> dict[str, Any]:
    users = _users(request)
    account = body.account.strip()
    key = await _guard_login(request, account)
    record = await asyncio.to_thread(users.get_login_record, account)
    if record is None or not verify_password(body.password, record["password_hash"]):
        await _record_failure(request, key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
    if record.get("disabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")
    if key is not None:
        await request.app.state.redis.delete(key)
    await asyncio.to_thread(users.touch_login, record["id"])
    return {"token": _token_for(record), "user": _public(record, await _membership(request, record["id"]))}


@router.get("/me")
async def me(request: Request, identity: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    user = await asyncio.to_thread(_users(request).get_user_by_id, identity["user_id"])
    return {"user": _public(user, await _membership(request, user["id"]))}


@router.post("/password")
async def change_password(body: PasswordBody, request: Request, identity: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    """修改密码：成功后返回新令牌，其他设备上的旧令牌立即失效。"""
    users = _users(request)
    current = await asyncio.to_thread(users.get_password_hash, identity["user_id"])
    if current is None or not verify_password(body.oldPassword, current):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码不正确")
    if body.oldPassword == body.newPassword:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码不能与原密码相同")
    user = await asyncio.to_thread(users.change_password, identity["user_id"], hash_password(body.newPassword))
    return {"token": _token_for(user), "user": _public(user, await _membership(request, user["id"]))}
