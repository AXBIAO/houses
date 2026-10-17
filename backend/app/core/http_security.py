"""给所有响应加安全头。用纯 ASGI 中间件实现，不影响 SSE 等流式响应。"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

Scope = dict[str, Any]
Message = dict[str, Any]
ASGIApp = Callable[[Scope, Callable[[], Awaitable[Message]], Callable[[Message], Awaitable[None]]], Awaitable[None]]

BASE_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    # 地图找房与「附近房源」需要定位，其余敏感能力一律关闭
    (b"permissions-policy", b"geolocation=(self), camera=(), microphone=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
)
HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.headers = BASE_HEADERS + ((HSTS,) if hsts else ())

    async def __call__(self, scope: Scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in self.headers if k not in existing]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)
