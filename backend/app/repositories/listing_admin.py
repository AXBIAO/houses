"""房源管理：房东后台（按 landlord_id 限定）与平台审核。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from psycopg import errors as pg_errors

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import Conflict, NotFound
from backend.app.domain.listing_search import PRICE_EXPR
from backend.app.repositories.sql_helpers import like_pattern, set_clause

EDITABLE = frozenset({
    "estate_id", "building", "unit_no", "rent_type", "title", "description", "bedrooms", "halls", "baths", "area",
    "floor", "total_floors", "orientation", "price_month", "price_night", "deposit_months", "min_months", "min_nights",
    "tags", "available_from",
})
ROW_COLUMNS = (
    "l.id, l.landlord_id, l.estate_id, e.name AS estate_name, e.district, l.building, l.unit_no, l.rent_type, l.title, "
    "l.description, l.bedrooms, l.halls, l.baths, l.area, l.floor, l.total_floors, l.orientation, l.price_month, "
    "l.price_night, l.deposit_months, l.min_months, l.min_nights, l.tags, l.cover_url, l.status, l.recommended, "
    "l.available_from, l.published_at, l.created_at, l.updated_at"
)
FROM = "FROM listings l JOIN estates e ON e.id = l.estate_id"


@dataclass(frozen=True)
class PriceChange:
    old_price: int | None
    new_price: int | None
    comparable: bool

    @property
    def dropped(self) -> bool:
        """仅上架中、价格单位未变（月价 ↔ 晚价不可比）且确实降价时才算降价。"""
        return self.comparable and self.old_price is not None and self.new_price is not None and self.new_price < self.old_price
TRANSITIONS = {"published": ("draft", "offline"), "offline": ("published",)}


def _check_estate(conn, landlord_id: int, estate_id: int) -> None:
    if conn.execute("SELECT 1 FROM estates WHERE id = %s AND landlord_id = %s", (estate_id, landlord_id)).fetchone() is None:
        raise NotFound("小区不存在")


def _lock_listing(conn, landlord_id: int, listing_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT id, status FROM listings WHERE id = %s AND landlord_id = %s FOR UPDATE",
                       (listing_id, landlord_id)).fetchone()
    if row is None:
        raise NotFound("房源不存在")
    return row


def _refresh_cover(conn, listing_id: int) -> None:
    conn.execute(
        "UPDATE listings SET cover_url = (SELECT url FROM listing_images WHERE listing_id = %s ORDER BY sort, id LIMIT 1), "
        "updated_at = now() WHERE id = %s",
        (listing_id, listing_id),
    )


class ListingAdminRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    # ---- 查询 ----------------------------------------------------------

    def list(self, landlord_id: int | None, *, status: str | None, keyword: str | None,
             limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        """landlord_id 为 None 仅供平台审核使用。"""
        clauses, params = ["TRUE"], []
        if landlord_id is not None:
            clauses.append("l.landlord_id = %s")
            params.append(landlord_id)
        if status:
            clauses.append("l.status = %s")
            params.append(status)
        if keyword:
            clauses.append("(l.title ILIKE %s OR e.name ILIKE %s)")
            params.extend([like_pattern(keyword)] * 2)
        where = " AND ".join(clauses)
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n {FROM} WHERE {where}", params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {ROW_COLUMNS}, d.name AS landlord_name, "
                "(SELECT count(*) FROM listing_inquiries q WHERE q.listing_id = l.id AND q.status = 'new') AS new_inquiries "
                f"{FROM} JOIN landlords d ON d.id = l.landlord_id WHERE {where} "
                "ORDER BY l.updated_at DESC, l.id DESC LIMIT %s OFFSET %s",
                (*params, limit, offset),
            ).fetchall()
        return rows, total

    def get(self, landlord_id: int, listing_id: int) -> dict[str, Any]:
        with self._db.transaction() as conn:
            row = conn.execute(f"SELECT {ROW_COLUMNS} {FROM} WHERE l.landlord_id = %s AND l.id = %s",
                               (landlord_id, listing_id)).fetchone()
            if row is None:
                raise NotFound("房源不存在")
            images = conn.execute("SELECT id, url, sort FROM listing_images WHERE listing_id = %s ORDER BY sort, id",
                                  (listing_id,)).fetchall()
            blocks = conn.execute(
                "SELECT id, start_date, end_date, kind, note FROM listing_unavailability WHERE listing_id = %s "
                "ORDER BY start_date", (listing_id,)
            ).fetchall()
        return {**row, "images": images, "unavailable": blocks}

    # ---- 增删改 --------------------------------------------------------

    def create(self, landlord_id: int, data: dict[str, Any]) -> int:
        _, values = set_clause(data, EDITABLE)
        columns = ", ".join(data)
        try:
            with self._db.transaction() as conn:
                _check_estate(conn, landlord_id, data["estate_id"])
                return conn.execute(
                    f"INSERT INTO listings (landlord_id, {columns}) VALUES (%s, {', '.join(['%s'] * len(values))}) RETURNING id",
                    (landlord_id, *values),
                ).fetchone()["id"]
        except pg_errors.CheckViolation as exc:
            raise Conflict("房源数据不合法，请检查价格与租期") from exc

    def update(self, landlord_id: int, listing_id: int, data: dict[str, Any]) -> PriceChange:
        """返回改价前后的展示价，供订阅的降价通知判断。"""
        sets, values = set_clause(data, EDITABLE)
        try:
            with self._db.transaction() as conn:
                _lock_listing(conn, landlord_id, listing_id)
                if "estate_id" in data:
                    _check_estate(conn, landlord_id, data["estate_id"])
                before = conn.execute(f"SELECT {PRICE_EXPR} AS price, l.rent_type FROM listings l WHERE l.id = %s", (listing_id,)).fetchone()
                after = conn.execute(
                    f"UPDATE listings l SET {sets}, updated_at = now() WHERE l.id = %s RETURNING {PRICE_EXPR} AS price, l.rent_type, l.status",
                    (*values, listing_id),
                ).fetchone()
        except pg_errors.CheckViolation as exc:
            raise Conflict("房源数据不合法，请检查价格与租期") from exc
        same_unit = before["rent_type"] == after["rent_type"] or "short" not in (before["rent_type"], after["rent_type"])
        return PriceChange(before["price"], after["price"], after["status"] == "published" and same_unit)

    def set_status(self, landlord_id: int, listing_id: int, status: str) -> None:
        """上架每次都刷新 published_at，让重新上架的房源出现在「今日房源动态」。"""
        with self._db.transaction() as conn:
            current = _lock_listing(conn, landlord_id, listing_id)["status"]
            if current not in TRANSITIONS.get(status, ()):
                raise Conflict(f"当前状态不能执行该操作（{current} → {status}）")
            conn.execute(
                "UPDATE listings SET status = %s, published_at = CASE WHEN %s = 'published' THEN now() ELSE published_at END, "
                "updated_at = now() WHERE id = %s",
                (status, status, listing_id),
            )

    def delete(self, landlord_id: int, listing_id: int) -> list[str]:
        """返回被删除的图片地址，由调用方清理文件。上架中的房源需先下架。"""
        with self._db.transaction() as conn:
            if _lock_listing(conn, landlord_id, listing_id)["status"] == "published":
                raise Conflict("请先下架再删除")
            urls = [r["url"] for r in conn.execute("SELECT url FROM listing_images WHERE listing_id = %s", (listing_id,))]
            conn.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
        return urls

    # ---- 图片 ----------------------------------------------------------

    def add_image(self, landlord_id: int, listing_id: int, url: str, max_images: int) -> dict[str, Any]:
        with self._db.transaction() as conn:
            _lock_listing(conn, landlord_id, listing_id)
            stats = conn.execute("SELECT count(*) AS n, coalesce(max(sort), -1) AS top FROM listing_images WHERE listing_id = %s",
                                 (listing_id,)).fetchone()
            if stats["n"] >= max_images:
                raise Conflict(f"每套房源最多 {max_images} 张图片")
            row = conn.execute("INSERT INTO listing_images (listing_id, url, sort) VALUES (%s, %s, %s) RETURNING id, url, sort",
                               (listing_id, url, stats["top"] + 1)).fetchone()
            _refresh_cover(conn, listing_id)
        return row

    def image_count(self, landlord_id: int, listing_id: int) -> int:
        with self._db.transaction() as conn:
            _lock_listing(conn, landlord_id, listing_id)
            return conn.execute("SELECT count(*) AS n FROM listing_images WHERE listing_id = %s", (listing_id,)).fetchone()["n"]

    def delete_image(self, landlord_id: int, listing_id: int, image_id: int) -> str:
        with self._db.transaction() as conn:
            _lock_listing(conn, landlord_id, listing_id)
            row = conn.execute("DELETE FROM listing_images WHERE id = %s AND listing_id = %s RETURNING url",
                               (image_id, listing_id)).fetchone()
            if row is None:
                raise NotFound("图片不存在")
            _refresh_cover(conn, listing_id)
        return row["url"]

    def reorder_images(self, landlord_id: int, listing_id: int, image_ids: list[int]) -> None:
        with self._db.transaction() as conn:
            _lock_listing(conn, landlord_id, listing_id)
            existing = {r["id"] for r in conn.execute("SELECT id FROM listing_images WHERE listing_id = %s", (listing_id,))}
            if existing != set(image_ids) or len(image_ids) != len(existing):
                raise Conflict("图片列表已变化，请刷新后重试")
            for sort, image_id in enumerate(image_ids):
                conn.execute("UPDATE listing_images SET sort = %s WHERE id = %s", (sort, image_id))
            _refresh_cover(conn, listing_id)

    # ---- 不可租时段 ----------------------------------------------------

    def add_block(self, landlord_id: int, listing_id: int, start: date, end: date, note: str) -> dict[str, Any]:
        with self._db.transaction() as conn:
            _lock_listing(conn, landlord_id, listing_id)
            return conn.execute(
                "INSERT INTO listing_unavailability (listing_id, start_date, end_date, kind, note) "
                "VALUES (%s, %s, %s, 'block', %s) RETURNING id, start_date, end_date, kind, note",
                (listing_id, start, end, note),
            ).fetchone()

    def delete_block(self, landlord_id: int, listing_id: int, block_id: int) -> None:
        with self._db.transaction() as conn:
            _lock_listing(conn, landlord_id, listing_id)
            # P3 签约/预订写入的时段由业务流程维护，后台只允许删除手动封禁
            row = conn.execute("DELETE FROM listing_unavailability WHERE id = %s AND listing_id = %s AND kind = 'block' RETURNING id",
                               (block_id, listing_id)).fetchone()
            if row is None:
                raise NotFound("时段不存在或不可手动删除")

    # ---- 平台审核 ------------------------------------------------------

    def moderate(self, listing_id: int, *, status: str | None, recommended: bool | None) -> None:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT status FROM listings WHERE id = %s FOR UPDATE", (listing_id,)).fetchone()
            if row is None:
                raise NotFound("房源不存在")
            if status == "offline" and row["status"] != "published":
                raise Conflict("只能下架已上架的房源")
            conn.execute(
                "UPDATE listings SET status = coalesce(%s, status), recommended = coalesce(%s, recommended), "
                "updated_at = now() WHERE id = %s",
                (status, recommended, listing_id),
            )
