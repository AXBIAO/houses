"""租客资料与收费项目（房东维度）。"""
from __future__ import annotations

from typing import Any

from psycopg import errors as pg_errors

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.sql_helpers import like_pattern, set_clause

RENTER_COLUMNS = "r.id, r.name, r.phone, r.id_card_tail, r.note, r.created_at"
RENTER_FIELDS = frozenset({"name", "phone", "id_card_tail", "note"})
FEE_COLUMNS = "f.id, f.name, f.kind, f.default_price, f.unit, f.active, f.created_at"
FEE_FIELDS = frozenset({"name", "kind", "default_price", "unit", "active"})
OPEN_LEASE = "('pending', 'active', 'expired')"


class RenterRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    # ---- 租客 ----------------------------------------------------------

    def list_renters(self, landlord_id: int, keyword: str | None) -> list[dict[str, Any]]:
        where, params = "r.landlord_id = %s", [landlord_id]
        if keyword:
            where += " AND (r.name ILIKE %s OR r.phone ILIKE %s)"
            params += [like_pattern(keyword)] * 2
        with self._db.transaction() as conn:
            return conn.execute(
                f"SELECT {RENTER_COLUMNS}, (SELECT count(*) FROM leases l WHERE l.renter_id = r.id "
                f"AND l.status IN {OPEN_LEASE}) AS open_leases FROM renters r WHERE {where} ORDER BY r.id DESC LIMIT 200",
                params,
            ).fetchall()

    def create_renter(self, landlord_id: int, data: dict[str, Any], conn=None) -> dict[str, Any]:
        """可传入外部事务（签约时同时新建租客）。"""
        set_clause(data, RENTER_FIELDS)
        sql = (f"INSERT INTO renters AS r (landlord_id, {', '.join(data)}) VALUES (%s, {', '.join(['%s'] * len(data))}) "
               f"RETURNING {RENTER_COLUMNS}")
        if conn is not None:
            return conn.execute(sql, (landlord_id, *data.values())).fetchone()
        with self._db.transaction() as own:
            return own.execute(sql, (landlord_id, *data.values())).fetchone()

    def update_renter(self, landlord_id: int, renter_id: int, data: dict[str, Any]) -> dict[str, Any]:
        sets, values = set_clause(data, RENTER_FIELDS)
        with self._db.transaction() as conn:
            row = conn.execute(
                f"UPDATE renters r SET {sets}, updated_at = now() WHERE r.landlord_id = %s AND r.id = %s RETURNING {RENTER_COLUMNS}",
                (*values, landlord_id, renter_id),
            ).fetchone()
        if row is None:
            raise NotFound("租客不存在")
        return row

    def delete_renter(self, landlord_id: int, renter_id: int) -> None:
        with self._db.transaction() as conn:
            if conn.execute("SELECT 1 FROM renters WHERE id = %s AND landlord_id = %s FOR UPDATE",
                            (renter_id, landlord_id)).fetchone() is None:
                raise NotFound("租客不存在")
            if conn.execute("SELECT 1 FROM leases WHERE renter_id = %s LIMIT 1", (renter_id,)).fetchone():
                raise Conflict("租客有租约记录，不能删除")
            conn.execute("DELETE FROM renters WHERE id = %s", (renter_id,))

    # ---- 收费项目 ------------------------------------------------------

    def list_fee_items(self, landlord_id: int, *, active_only: bool = False) -> list[dict[str, Any]]:
        where = "f.landlord_id = %s" + (" AND f.active" if active_only else "")
        with self._db.transaction() as conn:
            return conn.execute(f"SELECT {FEE_COLUMNS} FROM fee_items f WHERE {where} ORDER BY f.kind, f.id",
                                (landlord_id,)).fetchall()

    def create_fee_item(self, landlord_id: int, data: dict[str, Any]) -> dict[str, Any]:
        set_clause(data, FEE_FIELDS)
        try:
            with self._db.transaction() as conn:
                return conn.execute(
                    f"INSERT INTO fee_items AS f (landlord_id, {', '.join(data)}) VALUES (%s, {', '.join(['%s'] * len(data))}) "
                    f"RETURNING {FEE_COLUMNS}",
                    (landlord_id, *data.values()),
                ).fetchone()
        except pg_errors.UniqueViolation as exc:
            raise Conflict("已有同名收费项目") from exc

    def update_fee_item(self, landlord_id: int, item_id: int, data: dict[str, Any]) -> dict[str, Any]:
        sets, values = set_clause(data, FEE_FIELDS)
        try:
            with self._db.transaction() as conn:
                current = conn.execute("SELECT kind FROM fee_items WHERE id = %s AND landlord_id = %s FOR UPDATE",
                                       (item_id, landlord_id)).fetchone()
                if current is None:
                    raise NotFound("收费项目不存在")
                used = conn.execute("SELECT 1 FROM lease_fees WHERE fee_item_id = %s LIMIT 1", (item_id,)).fetchone()
                if used and data.get("kind", current["kind"]) != current["kind"]:
                    raise Conflict("已被租约使用的项目不能修改计费方式")
                return conn.execute(f"UPDATE fee_items f SET {sets} WHERE f.id = %s RETURNING {FEE_COLUMNS}",
                                    (*values, item_id)).fetchone()
        except pg_errors.UniqueViolation as exc:
            raise Conflict("已有同名收费项目") from exc

    def delete_fee_item(self, landlord_id: int, item_id: int) -> None:
        with self._db.transaction() as conn:
            if conn.execute("SELECT 1 FROM fee_items WHERE id = %s AND landlord_id = %s FOR UPDATE",
                            (item_id, landlord_id)).fetchone() is None:
                raise NotFound("收费项目不存在")
            used = conn.execute(
                "SELECT 1 FROM lease_fees WHERE fee_item_id = %s UNION ALL SELECT 1 FROM meter_readings WHERE fee_item_id = %s "
                "UNION ALL SELECT 1 FROM bill_items WHERE fee_item_id = %s LIMIT 1",
                (item_id, item_id, item_id),
            ).fetchone()
            if used:
                raise Conflict("项目已被使用，不能删除，可改为停用")
            conn.execute("DELETE FROM fee_items WHERE id = %s", (item_id,))
