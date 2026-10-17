"""房东查看与跟进咨询。"""
from __future__ import annotations

from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import NotFound

COLUMNS = (
    "q.id, q.listing_id, l.title AS listing_title, q.name, q.phone, q.message, q.move_in, q.move_out, "
    "q.status, q.note, q.created_at, q.handled_at"
)


class InquiryRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def list(self, landlord_id: int, *, status: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        where, params = "q.landlord_id = %s", [landlord_id]
        if status:
            where += " AND q.status = %s"
            params.append(status)
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n FROM listing_inquiries q WHERE {where}", params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {COLUMNS} FROM listing_inquiries q JOIN listings l ON l.id = q.listing_id "
                f"WHERE {where} ORDER BY q.status = 'new' DESC, q.created_at DESC LIMIT %s OFFSET %s",
                (*params, limit, offset),
            ).fetchall()
        return rows, total

    def update(self, landlord_id: int, inquiry_id: int, *, status: str, note: str | None) -> dict[str, Any]:
        with self._db.transaction() as conn:
            row = conn.execute(
                "UPDATE listing_inquiries q SET status = %s, note = coalesce(%s, q.note), "
                "handled_at = CASE WHEN %s = 'new' THEN NULL ELSE coalesce(q.handled_at, now()) END "
                "FROM listings l WHERE l.id = q.listing_id AND q.landlord_id = %s AND q.id = %s "
                f"RETURNING {COLUMNS}",
                (status, note, status, landlord_id, inquiry_id),
            ).fetchone()
        if row is None:
            raise NotFound("咨询不存在")
        return row
