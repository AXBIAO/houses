"""运行时配置：大模型与邮件优先使用后台「系统设置」里保存的值，未设置时回退到环境变量。

读取带 30 秒缓存，后台保存后立即失效，不需要重启服务。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Literal

from backend.app.core.config import settings
from backend.app.core.secret_box import decrypt

CACHE_SECONDS = 30.0
Source = Literal["db", "env", "none"]


@dataclass(frozen=True)
class LlmConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: float = 30.0
    source: Source = "none"

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


@dataclass(frozen=True)
class SmtpConfig:
    host: str = ""
    port: int = 465
    user: str = ""
    password: str = ""
    sender: str = ""
    use_tls: bool = True
    source: Source = "none"

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.sender)


def llm_from_env() -> LlmConfig:
    config = LlmConfig(settings.openai_base_url, settings.openai_api_key, settings.chat_model_name, settings.llm_request_timeout)
    return LlmConfig(**{**config.__dict__, "source": "env" if config.enabled else "none"})


def smtp_from_env() -> SmtpConfig:
    config = SmtpConfig(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password,
                        settings.smtp_from, settings.smtp_use_tls)
    return SmtpConfig(**{**config.__dict__, "source": "env" if config.enabled else "none"})


def llm_from_db(value: dict[str, Any]) -> LlmConfig:
    return LlmConfig(
        base_url=str(value.get("baseUrl") or ""), model=str(value.get("model") or ""),
        api_key=decrypt(value["apiKey"]) or "" if value.get("apiKey") else "",
        timeout=float(value.get("timeout") or 30.0), source="db",
    )


def smtp_from_db(value: dict[str, Any]) -> SmtpConfig:
    return SmtpConfig(
        host=str(value.get("host") or ""), port=int(value.get("port") or 465), user=str(value.get("user") or ""),
        password=decrypt(value["password"]) or "" if value.get("password") else "",
        sender=str(value.get("sender") or ""), use_tls=bool(value.get("useTls", True)), source="db",
    )


class RuntimeConfig:
    def __init__(self, repo) -> None:
        self._repo = repo
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _load(self, key: str, from_db, from_env):
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        value = await asyncio.to_thread(self._repo.get, key)
        config = from_db(value) if value else from_env()
        self._cache[key] = (time.monotonic() + CACHE_SECONDS, config)
        return config

    async def llm(self) -> LlmConfig:
        return await self._load("llm", llm_from_db, llm_from_env)

    async def smtp(self) -> SmtpConfig:
        return await self._load("smtp", smtp_from_db, smtp_from_env)

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)
