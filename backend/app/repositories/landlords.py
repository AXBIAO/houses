"""房东（商户）与成员关系。"""
from __future__ import annotations

from typing import Any

from psycopg import errors as pg_errors

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.sql_helpers import like_pattern, set_clause

LANDLORD_COLUMNS = "d.id, d.name, d.contact_name, d.contact_phone, d.status, d.created_at"
UPDATABLE = frozenset({"name", "contact_name", "contact_phone", "status"})


class LandlordRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    # ---- 成员身份 -------------------------------------------------------

    def membership_for_user(self, user_id: int) -> dict[str, Any] | None:
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT m.landlord_id, m.role, d.name, d.status FROM landlord_members m "
                "JOIN landlords d ON d.id = m.landlord_id WHERE m.user_id = %s",
                (user_id,),
            ).fetchone()

    def list_members(self, landlord_id: int) -> list[dict[str, Any]]:
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT u.id AS user_id, u.username, u.email, u.phone, m.role, m.created_at "
                "FROM landlord_members m JOIN users u ON u.id = m.user_id "
                "WHERE m.landlord_id = %s ORDER BY m.role DESC, m.created_at",
                (landlord_id,),
            ).fetchall()

    def add_member(self, landlord_id: int, user_id: int, role: str) -> None:
        try:
            with self._db.transaction() as conn:
                conn.execute("INSERT INTO landlord_members (landlord_id, user_id, role) VALUES (%s, %s, %s)",
                             (landlord_id, user_id, role))
        except pg_errors.UniqueViolation as exc:
            raise Conflict("该账号已属于某个房东") from exc

    def remove_member(self, landlord_id: int, user_id: int) -> None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT role FROM landlord_members WHERE landlord_id = %s AND user_id = %s FOR UPDATE",
                (landlord_id, user_id),
            ).fetchone()
            if row is None:
                raise NotFound("成员不存在")
            if row["role"] == "owner":
                owners = conn.execute(
                    "SELECT count(*) AS n FROM landlord_members WHERE landlord_id = %s AND role = 'owner'", (landlord_id,)
                ).fetchone()["n"]
                if owners <= 1:
                    raise Conflict("至少保留一个主账号")
            conn.execute("DELETE FROM landlord_members WHERE landlord_id = %s AND user_id = %s", (landlord_id, user_id))

    # ---- 平台管理 -------------------------------------------------------

    def list_landlords(self, *, keyword: str | None, status: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        clauses, params = ["TRUE"], []
        if keyword:
            clauses.append("(d.name ILIKE %s OR d.contact_phone ILIKE %s)")
            params.extend([like_pattern(keyword)] * 2)
        if status:
            clauses.append("d.status = %s")
            params.append(status)
        where = " AND ".join(clauses)
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n FROM landlords d WHERE {where}", params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {LANDLORD_COLUMNS}, "
                "(SELECT count(*) FROM listings l WHERE l.landlord_id = d.id) AS listing_count, "
                "(SELECT count(*) FROM listings l WHERE l.landlord_id = d.id AND l.status = 'published') AS published_count, "
                "(SELECT count(*) FROM landlord_members m WHERE m.landlord_id = d.id) AS member_count, "
                "(SELECT string_agg(coalesce(u.email, u.phone), ', ') FROM landlord_members m JOIN users u ON u.id = m.user_id "
                " WHERE m.landlord_id = d.id AND m.role = 'owner') AS owners "
                f"FROM landlords d WHERE {where} ORDER BY d.id DESC LIMIT %s OFFSET %s",
                (*params, limit, offset),
            ).fetchall()
        return rows, total

    def get(self, landlord_id: int) -> dict[str, Any] | None:
        with self._db.transaction() as conn:
            return conn.execute(f"SELECT {LANDLORD_COLUMNS} FROM landlords d WHERE d.id = %s", (landlord_id,)).fetchone()

    def create(self, *, name: str, contact_name: str | None, contact_phone: str | None, owner_user_id: int) -> dict[str, Any]:
        """开通房东并指定主账号，同一事务内完成，任一步失败都不留半成品。"""
        try:
            with self._db.transaction() as conn:
                row = conn.execute(
                    "INSERT INTO landlords (name, contact_name, contact_phone) VALUES (%s, %s, %s) "
                    "RETURNING id, name, contact_name, contact_phone, status, created_at",
                    (name, contact_name, contact_phone),
                ).fetchone()
                conn.execute("INSERT INTO landlord_members (landlord_id, user_id, role) VALUES (%s, %s, 'owner')",
                             (row["id"], owner_user_id))
                return row
        except pg_errors.UniqueViolation as exc:
            raise Conflict("该账号已属于某个房东") from exc

    def update(self, landlord_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        sets, values = set_clause(fields, UPDATABLE)
        if not sets:
            row = self.get(landlord_id)
        else:
            with self._db.transaction() as conn:
                row = conn.execute(
                    f"UPDATE landlords d SET {sets}, updated_at = now() WHERE d.id = %s RETURNING {LANDLORD_COLUMNS}",
                    (*values, landlord_id),
                ).fetchone()
        if row is None:
            raise NotFound("房东不存在")
        return row

    # ---- 房东概览 -------------------------------------------------------

    def overview(self, landlord_id: int) -> dict[str, Any]:
        with self._db.transaction() as conn:
            listings = conn.execute(
                "SELECT status, count(*) AS n FROM listings WHERE landlord_id = %s GROUP BY status", (landlord_id,)
            ).fetchall()
            inquiries = conn.execute(
                "SELECT count(*) FILTER (WHERE status = 'new') AS new_count, "
                "count(*) FILTER (WHERE created_at >= now() - interval '7 days') AS week_count "
                "FROM listing_inquiries WHERE landlord_id = %s",
                (landlord_id,),
            ).fetchone()
            estates = conn.execute("SELECT count(*) AS n FROM estates WHERE landlord_id = %s", (landlord_id,)).fetchone()["n"]
        by_status = {r["status"]: r["n"] for r in listings}
        return {
            "listings": {s: by_status.get(s, 0) for s in ("draft", "published", "offline")},
            "estates": estates,
            "newInquiries": inquiries["new_count"],
            "weekInquiries": inquiries["week_count"],
        }
