"""后台「系统设置」：大模型与邮件服务。仅超级管理员可查看和修改；密钥加密存库，接口只回显末 4 位。"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.api.routes_ai import _vocabulary
from backend.app.core.auth import RequireSuperAdmin
from backend.app.core.llm import probe_llm
from backend.app.core.mailer import deliver
from backend.app.core.secret_box import encrypt, tail
from backend.app.services.runtime_config import LlmConfig, SmtpConfig, llm_from_db, smtp_from_db

router = APIRouter(prefix="/api/admin/settings", tags=["settings"])

DEFAULT_PROBE = "高新区两室，5000 以内，近地铁"


def _url(value: str) -> str:
    value = value.strip()
    if value and not value.startswith(("https://", "http://")):
        raise ValueError("地址需以 https:// 或 http:// 开头")
    return value.rstrip("/")


class LlmIn(BaseModel):
    baseUrl: str = Field("", max_length=300)
    model: str = Field("", max_length=100)
    # None = 保持不变；"" = 清空
    apiKey: str | None = Field(None, max_length=500)
    timeout: float = Field(30.0, ge=3, le=120)

    @field_validator("baseUrl")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _url(value)


class SmtpIn(BaseModel):
    host: str = Field("", max_length=200)
    port: int = Field(465, ge=1, le=65535)
    user: str = Field("", max_length=200)
    password: str | None = Field(None, max_length=500)
    sender: str = Field("", max_length=200)
    useTls: bool = True


class ProbeIn(BaseModel):
    query: str = Field(DEFAULT_PROBE, min_length=1, max_length=200)


class MailTestIn(BaseModel):
    to: EmailStr


def _state(request: Request):
    return request.app.state


def _llm_view(config: LlmConfig) -> dict[str, Any]:
    return {"source": config.source, "enabled": config.enabled, "baseUrl": config.base_url, "model": config.model,
            "timeout": config.timeout, "apiKeySet": bool(config.api_key), "apiKeyTail": tail(config.api_key)}


def _smtp_view(config: SmtpConfig) -> dict[str, Any]:
    return {"source": config.source, "enabled": config.enabled, "host": config.host, "port": config.port, "user": config.user,
            "sender": config.sender, "useTls": config.use_tls, "passwordSet": bool(config.password), "passwordTail": tail(config.password)}


def _merge_secret(new: str | None, old_cipher: str | None) -> str | None:
    if new is None:
        return old_cipher
    new = new.strip()
    return encrypt(new) if new else None


@router.get("")
async def get_settings(request: Request, _admin: dict = Depends(RequireSuperAdmin)) -> dict[str, Any]:
    runtime = _state(request).runtime
    llm, smtp = await asyncio.gather(runtime.llm(), runtime.smtp())
    return {"llm": _llm_view(llm), "smtp": _smtp_view(smtp)}


@router.put("/llm")
async def put_llm(body: LlmIn, request: Request, admin: dict = Depends(RequireSuperAdmin)) -> dict[str, Any]:
    repo = _state(request).app_settings
    old = await asyncio.to_thread(repo.get, "llm") or {}
    value = {"baseUrl": body.baseUrl, "model": body.model.strip(), "timeout": body.timeout,
             "apiKey": _merge_secret(body.apiKey, old.get("apiKey"))}
    await asyncio.to_thread(repo.put, "llm", value, admin["user_id"])
    _state(request).runtime.invalidate("llm")
    return _llm_view(llm_from_db(value))


@router.put("/smtp")
async def put_smtp(body: SmtpIn, request: Request, admin: dict = Depends(RequireSuperAdmin)) -> dict[str, Any]:
    repo = _state(request).app_settings
    old = await asyncio.to_thread(repo.get, "smtp") or {}
    value = {"host": body.host.strip(), "port": body.port, "user": body.user.strip(), "sender": body.sender.strip(),
             "useTls": body.useTls, "password": _merge_secret(body.password, old.get("password"))}
    await asyncio.to_thread(repo.put, "smtp", value, admin["user_id"])
    _state(request).runtime.invalidate("smtp")
    return _smtp_view(smtp_from_db(value))


@router.delete("/{key}")
async def reset_setting(key: str, request: Request, _admin: dict = Depends(RequireSuperAdmin)) -> dict[str, Any]:
    """清除后台保存的配置，回退到环境变量。"""
    if key in ("llm", "smtp"):
        await asyncio.to_thread(_state(request).app_settings.delete, key)
        _state(request).runtime.invalidate(key)
    return await get_settings(request, _admin)


@router.post("/llm/test")
async def test_llm(body: ProbeIn, request: Request, _admin: dict = Depends(RequireSuperAdmin)) -> dict[str, Any]:
    config = await _state(request).runtime.llm()
    return await probe_llm(config, await _vocabulary(request), date.today(), body.query)


@router.post("/smtp/test")
async def test_smtp(body: MailTestIn, request: Request, _admin: dict = Depends(RequireSuperAdmin)) -> dict[str, Any]:
    config = await _state(request).runtime.smtp()
    error = await deliver(str(body.to), "[房子 Houses] 测试邮件", "这是一封测试邮件：邮件通知已配置成功。", config)
    return {"ok": error is None, "message": error or f"已发送到 {body.to}"}
