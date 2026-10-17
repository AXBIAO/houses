"""房源公开读取与咨询写入（PostgreSQL）。"""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.listing_search import (
    FROM_PUBLIC,
    SUMMARY_COLUMNS,
    ListingFilters,
    compile_filters,
)

TODAY_WINDOW_HOURS = 24


class ListingRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def search(self, filters: ListingFilters, *, today: date, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        q = compile_filters(filters, today)
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n {FROM_PUBLIC} WHERE {q.where}", q.params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {SUMMARY_COLUMNS}{q.distance_select} {FROM_PUBLIC} WHERE {q.where} "
                f"ORDER BY {q.order_by} LIMIT %s OFFSET %s",
                (*q.distance_params, *q.params, limit, offset),
            ).fetchall()
        return rows, total

    def home_feed(self, *, today: date, limit: int) -> dict[str, list[dict[str, Any]]]:
        """今日动态：24 小时内上架的优先，不足时用最近上架补齐。"""
        base = compile_filters(ListingFilters(), today)
        with self._db.transaction() as conn:
            latest = conn.execute(
                f"SELECT {SUMMARY_COLUMNS}, (l.published_at >= now() - make_interval(hours => %s)) AS is_today "
                f"{FROM_PUBLIC} WHERE {base.where} ORDER BY l.published_at DESC, l.id DESC LIMIT %s",
                (TODAY_WINDOW_HOURS, *base.params, limit),
            ).fetchall()
            recommended = conn.execute(
                f"SELECT {SUMMARY_COLUMNS} {FROM_PUBLIC} WHERE {base.where} AND l.recommended "
                "ORDER BY l.published_at DESC, l.id DESC LIMIT %s",
                (*base.params, limit),
            ).fetchall()
            today_count = conn.execute(
                f"SELECT count(*) AS n {FROM_PUBLIC} WHERE {base.where} "
                "AND l.published_at >= now() - make_interval(hours => %s)",
                (*base.params, TODAY_WINDOW_HOURS),
            ).fetchone()["n"]
        return {"today": latest, "recommended": recommended, "todayCount": today_count}

    def facets(self) -> dict[str, list[dict[str, Any]]]:
        base = compile_filters(ListingFilters(), date.today())
        with self._db.transaction() as conn:
            districts = conn.execute(
                f"SELECT e.district AS value, count(*) AS count {FROM_PUBLIC} WHERE {base.where} "
                "GROUP BY e.district ORDER BY count(*) DESC, e.district LIMIT 50",
                base.params,
            ).fetchall()
            tags = conn.execute(
                f"SELECT t.tag AS value, count(*) AS count {FROM_PUBLIC} CROSS JOIN LATERAL unnest(l.tags) AS t(tag) "
                f"WHERE {base.where} GROUP BY t.tag ORDER BY count(*) DESC, t.tag LIMIT 30",
                base.params,
            ).fetchall()
        return {"districts": districts, "tags": tags}

    def sitemap_entries(self, limit: int) -> list[dict[str, Any]]:
        base = compile_filters(ListingFilters(), date.today())
        with self._db.transaction() as conn:
            return conn.execute(
                f"SELECT l.id, l.updated_at {FROM_PUBLIC} WHERE {base.where} ORDER BY l.updated_at DESC LIMIT %s",
                (*base.params, limit),
            ).fetchall()

    def communities(self, limit: int = 200) -> list[str]:
        """有上架房源的小区名，供 AI 找房识别小区。"""
        base = compile_filters(ListingFilters(), date.today())
        with self._db.transaction() as conn:
            rows = conn.execute(
                f"SELECT e.name, count(*) AS n {FROM_PUBLIC} WHERE {base.where} GROUP BY e.name ORDER BY count(*) DESC LIMIT %s",
                (*base.params, limit),
            ).fetchall()
        return [r["name"] for r in rows]

    def get_public(self, listing_id: int, *, today: date) -> dict[str, Any] | None:
        base = compile_filters(ListingFilters(), today)
        with self._db.transaction() as conn:
            row = conn.execute(
                f"SELECT {SUMMARY_COLUMNS}, l.description, l.building, l.total_floors, l.orientation, "
                "l.deposit_months, l.min_months, l.min_nights, l.landlord_id, e.address, d.name AS landlord_name "
                f"{FROM_PUBLIC} WHERE {base.where} AND l.id = %s",
                (*base.params, listing_id),
            ).fetchone()
            if row is None:
                return None
            images = conn.execute(
                "SELECT url FROM listing_images WHERE listing_id = %s ORDER BY sort, id", (listing_id,)
            ).fetchall()
            busy = conn.execute(
                "SELECT start_date, end_date FROM listing_unavailability "
                "WHERE listing_id = %s AND end_date > %s ORDER BY start_date LIMIT 50",
                (listing_id, today),
            ).fetchall()
        return {**row, "images": [r["url"] for r in images], "unavailable": busy}

    def create_inquiry(self, *, listing_id: int, landlord_id: int, user_id: int | None, name: str, phone: str,
                       message: str, move_in: date | None, move_out: date | None, client_ip: str | None) -> dict[str, Any]:
        with self._db.transaction() as conn:
            return conn.execute(
                "INSERT INTO listing_inquiries (listing_id, landlord_id, user_id, name, phone, message, move_in, move_out, client_ip) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, created_at",
                (listing_id, landlord_id, user_id, name, phone, message, move_in, move_out, client_ip),
            ).fetchone()
