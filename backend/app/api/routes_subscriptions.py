"""房源订阅、站内通知、SSE 实时推送。均需登录。"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from backend.app.api.serialize import camelize, camelize_all
from backend.app.core.auth import RequireUser
from backend.app.domain.listing_search import FilterError
from backend.app.domain.query_filters import normalize, to_filters

router = APIRouter(prefix="/api", tags=["subscriptions"])

HEARTBEAT_SECONDS = 25


class SubscriptionIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    filters: dict[str, Any] = Field(default_factory=dict)
    emailEnabled: bool = False
    active: bool = True

    @model_validator(mode="after")
    def _name(self) -> "SubscriptionIn":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("请填写订阅名称")
        return self


class ReadIn(BaseModel):
    ids: list[int] | None = Field(None, max_length=200)


def _repo(request: Request):
    return request.app.state.subscriptions


def _clean_filters(raw: dict[str, Any]) -> dict[str, str]:
    try:
        filters = normalize(raw)
        to_filters(filters, date.today())
    except FilterError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not filters:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "至少设置一个条件，否则每套新房源都会通知你")
    return filters


async def _with_counts(request: Request, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """附上「当前符合条件的房源数」，让用户知道订阅大概会收到多少。"""
    today = date.today()
    listings = request.app.state.listings

    async def count(row: dict[str, Any]) -> int:
        try:
            _, total = await asyncio.to_thread(listings.search, to_filters(row["filters"], today), today=today, limit=1, offset=0)
            return total
        except (FilterError, ValueError):
            return 0

    totals = await asyncio.gather(*(count(r) for r in rows))
    return [{**camelize(r), "matchCount": n} for r, n in zip(rows, totals)]


@router.get("/subscriptions")
async def list_subscriptions(request: Request, user: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    rows = await asyncio.to_thread(_repo(request).list, user["user_id"])
    return {"items": await _with_counts(request, rows), "emailAvailable": (await request.app.state.runtime.smtp()).enabled}


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_subscription(body: SubscriptionIn, request: Request, user: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    row = await asyncio.to_thread(_repo(request).create, user["user_id"], name=body.name,
                                  filters=_clean_filters(body.filters), email_enabled=body.emailEnabled)
    return (await _with_counts(request, [row]))[0]


@router.put("/subscriptions/{sub_id}")
async def update_subscription(sub_id: int, body: SubscriptionIn, request: Request,
                              user: dict[str, Any] = Depends(RequireUser)) -> dict[str, Any]:
    row = await asyncio.to_thread(_repo(request).update, user["user_id"], sub_id, name=body.name,
                                  filters=_clean_filters(body.filters), email_enabled=body.emailEnabled, active=body.active)
    return (await _with_counts(request, [row]))[0]


@router.delete("/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(sub_id: int, request: Request, user: dict[str, Any] = Depends(RequireUser)) -> Response:
    await asyncio.to_thread(_repo(request).delete, user["user_id"], sub_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notifications")
async def list_notifications(
    request: Request,
    unread: bool = False,
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(RequireUser),
) -> dict[str, Any]:
    rows, total, unread_count = await asyncio.to_thread(_repo(request).notifications, user["user_id"], unread_only=unread,
                                                        limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "unread": unread_count, "page": page, "pageSize": pageSize}


@router.post("/notifications/read")
async def mark_read(body: ReadIn, request: Request, user: dict[str, Any] = Depends(RequireUser)) -> dict[str, int]:
    """不传 ids 表示全部标为已读。"""
    return {"updated": await asyncio.to_thread(_repo(request).mark_read, user["user_id"], body.ids)}


@router.get("/notifications/stream")
async def stream(request: Request, user: dict[str, Any] = Depends(RequireUser)) -> StreamingResponse:
    hub = request.app.state.hub
    user_id = user["user_id"]

    async def events() -> AsyncIterator[str]:
        yield f"event: ready\ndata: {json.dumps({'userId': user_id})}\n\n"
        source = hub.stream(user_id)
        pending = asyncio.ensure_future(source.__anext__())
        try:
            while not await request.is_disconnected():
                done, _ = await asyncio.wait({pending}, timeout=HEARTBEAT_SECONDS)
                if not done:
                    yield ": ping\n\n"  # 心跳，防止代理断开空闲连接
                    continue
                yield f"event: notification\ndata: {pending.result()}\n\n"
                pending = asyncio.ensure_future(source.__anext__())
        finally:
            pending.cancel()
            # 先等被取消的读取结束，否则关闭仍在运行的生成器会报错
            await asyncio.gather(pending, return_exceptions=True)
            await source.aclose()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
