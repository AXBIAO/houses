"""订阅匹配与实时推送。

- 房源上架 / 降价后调用 match_listing：找出条件命中的订阅，写站内通知（唯一约束去重），再实时推送、按需发邮件；
- 推送走 Redis pub/sub（多实例共享），没有 Redis 时退化为进程内广播；
- SSE 连接通过 stream() 订阅当前用户的频道。
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import date
from typing import Any, AsyncIterator

from backend.app.core.config import settings
from backend.app.core.mailer import send_mail

logger = logging.getLogger("houses.notifier")
CHANNEL = "houses:notify:{user_id}"
LOCAL_QUEUE_SIZE = 100


class NotificationHub:
    def __init__(self, redis=None) -> None:
        self._redis = redis
        self._local: dict[int, set[asyncio.Queue[str]]] = defaultdict(set)

    async def publish(self, user_id: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str)
        if self._redis is not None:
            try:
                await self._redis.publish(CHANNEL.format(user_id=user_id), data)
                return
            except Exception as exc:  # Redis 抖动时退回进程内推送，至少本实例的连接能收到
                logger.warning("Redis 推送失败，改用进程内推送：%s", exc)
        for queue in list(self._local.get(user_id, ())):
            if not queue.full():
                queue.put_nowait(data)

    async def stream(self, user_id: int) -> AsyncIterator[str]:
        if self._redis is not None:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(CHANNEL.format(user_id=user_id))
            try:
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        data = message["data"]
                        yield data.decode() if isinstance(data, bytes) else data
            finally:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            return
        queue: asyncio.Queue[str] = asyncio.Queue(LOCAL_QUEUE_SIZE)
        self._local[user_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._local[user_id].discard(queue)


def _text(listing: dict[str, Any], kind: str, old_price: int | None) -> tuple[str, str]:
    unit = "晚" if listing["rent_type"] == "short" else "月"
    place = f"{listing['district']} · {listing['community']}"
    if kind == "price_drop" and old_price:
        return f"降价：{listing['title']}", f"¥{old_price} → ¥{listing['price']}/{unit} · {place}"
    return f"新房源：{listing['title']}", f"¥{listing['price']}/{unit} · {place}"


async def match_listing(state, listing_id: int, kind: str = "new", old_price: int | None = None) -> int:
    """返回新产生的通知数。房源已不公开（下架/房东停用）时什么都不做。"""
    today = date.today()
    listing = await asyncio.to_thread(state.listings.get_public, listing_id, today=today)
    if listing is None:
        return 0
    subs = await asyncio.to_thread(state.subscriptions.matching, listing_id, today)
    title, body = _text(listing, kind, old_price)
    created = 0
    for sub in subs:
        note = await asyncio.to_thread(
            state.subscriptions.add_notification, user_id=sub["user_id"], subscription_id=sub["id"],
            listing_id=listing_id, kind=kind, price=int(listing["price"] or 0), title=title, body=body,
        )
        if note is None:
            continue
        created += 1
        await state.hub.publish(sub["user_id"], {
            "type": "notification", "id": note["id"], "kind": kind, "title": title, "body": body,
            "listingId": listing_id, "subscriptionName": sub["name"],
        })
        if sub["email_enabled"] and sub["email"]:
            smtp = await state.runtime.smtp()
            link = f"{settings.public_base_url.rstrip('/')}/listings/{listing_id}"
            sent = await send_mail(sub["email"], f"[房子 Houses] {title}", f"{body}\n\n订阅：{sub['name']}\n查看：{link}\n", smtp)
            if sent:
                await asyncio.to_thread(state.subscriptions.mark_emailed, note["id"])
    return created


async def match_recent(state, minutes: int = 30) -> int:
    """补偿任务：重新匹配最近上架的房源，去重保证不会重复通知。"""
    ids = await asyncio.to_thread(state.subscriptions.recently_published, minutes)
    total = 0
    for listing_id in ids:
        total += await match_listing(state, listing_id)
    return total
