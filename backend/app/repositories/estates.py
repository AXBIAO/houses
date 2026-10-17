"""房东自己的小区。所有方法都以 landlord_id 限定范围。"""
from __future__ import annotations

from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.sql_helpers import set_clause

COLUMNS = "e.id, e.name, e.city, e.district, e.address, e.lat, e.lng, e.created_at, e.updated_at"
FIELDS = frozenset({"name", "city", "district", "address", "lat", "lng"})


class EstateRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def list(self, landlord_id: int) -> list[dict[str, Any]]:
        with self._db.transaction() as conn:
            return conn.execute(
                f"SELECT {COLUMNS}, (SELECT count(*) FROM listings l WHERE l.estate_id = e.id) AS listing_count "
                "FROM estates e WHERE e.landlord_id = %s ORDER BY e.id DESC",
                (landlord_id,),
            ).fetchall()

    def get(self, landlord_id: int, estate_id: int) -> dict[str, Any]:
        with self._db.transaction() as conn:
            row = conn.execute(f"SELECT {COLUMNS} FROM estates e WHERE e.landlord_id = %s AND e.id = %s",
                               (landlord_id, estate_id)).fetchone()
        if row is None:
            raise NotFound("小区不存在")
        return row

    def create(self, landlord_id: int, data: dict[str, Any]) -> dict[str, Any]:
        sets, values = set_clause(data, FIELDS)  # 校验字段白名单
        columns = ", ".join(data)
        placeholders = ", ".join(["%s"] * len(values))
        with self._db.transaction() as conn:
            return conn.execute(
                f"INSERT INTO estates AS e (landlord_id, {columns}) VALUES (%s, {placeholders}) RETURNING {COLUMNS}",
                (landlord_id, *values),
            ).fetchone()

    def update(self, landlord_id: int, estate_id: int, data: dict[str, Any]) -> dict[str, Any]:
        sets, values = set_clause(data, FIELDS)
        with self._db.transaction() as conn:
            row = conn.execute(
                f"UPDATE estates e SET {sets}, updated_at = now() WHERE e.landlord_id = %s AND e.id = %s RETURNING {COLUMNS}",
                (*values, landlord_id, estate_id),
            ).fetchone()
        if row is None:
            raise NotFound("小区不存在")
        return row

    def delete(self, landlord_id: int, estate_id: int) -> None:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT id FROM estates WHERE landlord_id = %s AND id = %s FOR UPDATE",
                               (landlord_id, estate_id)).fetchone()
            if row is None:
                raise NotFound("小区不存在")
            in_use = conn.execute("SELECT 1 FROM listings WHERE estate_id = %s LIMIT 1", (estate_id,)).fetchone()
            if in_use:
                raise Conflict("小区下还有房源，不能删除")
            conn.execute("DELETE FROM estates WHERE id = %s", (estate_id,))
