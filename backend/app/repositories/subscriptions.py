"""订阅与站内通知（PostgreSQL）。"""
from __future__ import annotations

from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import Conflict, NotFound
from backend.app.domain.listing_search import FROM_PUBLIC, FilterError, compile_filters
from backend.app.domain.query_filters import to_filters

MAX_SUBSCRIPTIONS = 10
SUB_COLUMNS = "s.id, s.name, s.filters, s.email_enabled, s.active, s.created_at, s.updated_at"
NOTIFICATION_COLUMNS = "n.id, n.subscription_id, n.listing_id, n.kind, n.price, n.title, n.body, n.read_at, n.created_at"


class SubscriptionRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    # ---- 订阅 ----------------------------------------------------------

    def list(self, user_id: int) -> list[dict[str, Any]]:
        with self._db.transaction() as conn:
            return conn.execute(
                f"SELECT {SUB_COLUMNS}, (SELECT count(*) FROM notifications n WHERE n.subscription_id = s.id "
                "AND n.read_at IS NULL) AS unread FROM subscriptions s WHERE s.user_id = %s ORDER BY s.id DESC",
                (user_id,),
            ).fetchall()

    def create(self, user_id: int, *, name: str, filters: dict[str, str], email_enabled: bool) -> dict[str, Any]:
        with self._db.transaction() as conn:
            # 锁住用户行，避免并发创建绕过数量上限
            conn.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
            count = conn.execute("SELECT count(*) AS n FROM subscriptions WHERE user_id = %s", (user_id,)).fetchone()["n"]
            if count >= MAX_SUBSCRIPTIONS:
                raise Conflict(f"最多保存 {MAX_SUBSCRIPTIONS} 个订阅")
            return conn.execute(
                f"INSERT INTO subscriptions AS s (user_id, name, filters, email_enabled) VALUES (%s, %s, %s, %s) RETURNING {SUB_COLUMNS}",
                (user_id, name, Jsonb(filters), email_enabled),
            ).fetchone()

    def update(self, user_id: int, sub_id: int, *, name: str, filters: dict[str, str], email_enabled: bool,
               active: bool) -> dict[str, Any]:
        with self._db.transaction() as conn:
            row = conn.execute(
                "UPDATE subscriptions s SET name = %s, filters = %s, email_enabled = %s, active = %s, updated_at = now() "
                f"WHERE s.id = %s AND s.user_id = %s RETURNING {SUB_COLUMNS}",
                (name, Jsonb(filters), email_enabled, active, sub_id, user_id),
            ).fetchone()
        if row is None:
            raise NotFound("订阅不存在")
        return row

    def delete(self, user_id: int, sub_id: int) -> None:
        with self._db.transaction() as conn:
            if conn.execute("DELETE FROM subscriptions WHERE id = %s AND user_id = %s RETURNING id", (sub_id, user_id)).fetchone() is None:
                raise NotFound("订阅不存在")

    # ---- 匹配 ----------------------------------------------------------

    def matching(self, listing_id: int, today: date) -> list[dict[str, Any]]:
        """返回条件命中该房源的启用中订阅。逐条复用公开检索的 SQL，规则与用户在列表页看到的一致。"""
        with self._db.transaction() as conn:
            subs = conn.execute(
                "SELECT s.id, s.user_id, s.name, s.filters, s.email_enabled, u.email FROM subscriptions s "
                "JOIN users u ON u.id = s.user_id WHERE s.active AND NOT u.disabled ORDER BY s.id",
            ).fetchall()
            hits = []
            for sub in subs:
                try:
                    q = compile_filters(to_filters(sub["filters"], today), today)
                except (FilterError, ValueError):
                    continue
                found = conn.execute(f"SELECT 1 {FROM_PUBLIC} WHERE {q.where} AND l.id = %s", (*q.params, listing_id)).fetchone()
                if found:
                    hits.append(sub)
        return hits

    def add_notification(self, *, user_id: int, subscription_id: int, listing_id: int, kind: str, price: int,
                         title: str, body: str) -> dict[str, Any] | None:
        """重复事件返回 None（唯一约束去重）。"""
        with self._db.transaction() as conn:
            return conn.execute(
                "INSERT INTO notifications AS n (user_id, subscription_id, listing_id, kind, price, title, body) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (subscription_id, listing_id, kind, price) DO NOTHING "
                f"RETURNING {NOTIFICATION_COLUMNS}",
                (user_id, subscription_id, listing_id, kind, price, title, body),
            ).fetchone()

    def mark_emailed(self, notification_id: int) -> None:
        with self._db.transaction() as conn:
            conn.execute("UPDATE notifications SET emailed_at = now() WHERE id = %s", (notification_id,))

    def recently_published(self, minutes: int) -> list[int]:
        with self._db.transaction() as conn:
            return [r["id"] for r in conn.execute(
                "SELECT id FROM listings WHERE status = 'published' AND published_at >= now() - make_interval(mins => %s)",
                (minutes,),
            ).fetchall()]

    # ---- 通知 ----------------------------------------------------------

    def notifications(self, user_id: int, *, unread_only: bool, limit: int, offset: int) -> tuple[list[dict[str, Any]], int, int]:
        where = "n.user_id = %s" + (" AND n.read_at IS NULL" if unread_only else "")
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n FROM notifications n WHERE {where}", (user_id,)).fetchone()["n"]
            unread = conn.execute("SELECT count(*) AS n FROM notifications WHERE user_id = %s AND read_at IS NULL",
                                  (user_id,)).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {NOTIFICATION_COLUMNS}, l.cover_url, s.name AS subscription_name FROM notifications n "
                "JOIN listings l ON l.id = n.listing_id LEFT JOIN subscriptions s ON s.id = n.subscription_id "
                f"WHERE {where} ORDER BY n.created_at DESC, n.id DESC LIMIT %s OFFSET %s",
                (user_id, limit, offset),
            ).fetchall()
        return rows, total, unread

    def mark_read(self, user_id: int, ids: list[int] | None) -> int:
        with self._db.transaction() as conn:
            if ids is None:
                cur = conn.execute("UPDATE notifications SET read_at = now() WHERE user_id = %s AND read_at IS NULL", (user_id,))
            else:
                cur = conn.execute("UPDATE notifications SET read_at = now() WHERE user_id = %s AND id = ANY(%s) AND read_at IS NULL",
                                   (user_id, ids))
            return cur.rowcount
