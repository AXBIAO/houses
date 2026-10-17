"""房源公开检索：筛选条件 → 参数化 SQL。

只拼接常量片段，所有用户输入都走 %s 参数；方便单测且无注入风险。
租期按半开区间 [start, end) 与 listing_unavailability 判重叠。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from backend.app.domain.dates import add_months

RentType = Literal["long", "short", "shared"]
SortKey = Literal["latest", "price_asc", "price_desc", "distance"]

RENT_TYPES: tuple[str, ...] = ("long", "short", "shared")
EARTH_RADIUS_KM = 6371.0
DEFAULT_NEARBY_RADIUS_KM = 5.0
MAX_STAY_DAYS = 3 * 366

# 卡片展示价：短租按晚，其余按月
PRICE_EXPR = "(CASE WHEN l.rent_type = 'short' THEN l.price_night ELSE l.price_month END)"

SUMMARY_COLUMNS = f"""
    l.id, l.title, l.rent_type, l.bedrooms, l.halls, l.baths, l.area, l.floor, l.tags, l.cover_url,
    l.price_month, l.price_night, {PRICE_EXPR} AS price, l.recommended, l.available_from, l.published_at,
    e.id AS estate_id, e.name AS community, e.city, e.district, e.lat, e.lng
"""

FROM_PUBLIC = """
    FROM listings l
    JOIN estates e ON e.id = l.estate_id
    JOIN landlords d ON d.id = l.landlord_id
"""


class FilterError(ValueError):
    """筛选参数自相矛盾（如退租早于入住），路由层转为 422。"""


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float


@dataclass(frozen=True)
class BBox:
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float


@dataclass(frozen=True)
class StayWindow:
    start: date
    end: date
    explicit_length: bool

    @property
    def nights(self) -> int:
        return (self.end - self.start).days

    @property
    def months(self) -> int:
        return self.nights // 30


@dataclass(frozen=True)
class ListingFilters:
    rent_type: RentType | None = None
    keyword: str | None = None
    district: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_bedrooms: int | None = None
    tags: tuple[str, ...] = ()
    move_in: date | None = None
    move_out: date | None = None
    months: int | None = None
    near: GeoPoint | None = None
    radius_km: float | None = None
    bbox: BBox | None = None
    recommended: bool | None = None
    exclude_id: int | None = None
    sort: SortKey = "latest"


@dataclass(frozen=True)
class CompiledQuery:
    where: str
    params: tuple[Any, ...]
    order_by: str
    distance_select: str = ""
    distance_params: tuple[Any, ...] = field(default=())


def resolve_stay(filters: ListingFilters, today: date) -> StayWindow | None:
    """把入住日 / 退租日 / 月数统一成区间；三者都没给时不做可租判断。"""
    if filters.move_in is None and filters.move_out is None and filters.months is None:
        return None
    start = filters.move_in or today
    if start < today:
        raise FilterError("入住日期不能早于今天")
    if filters.move_out is not None:
        end, explicit = filters.move_out, True
    elif filters.months is not None:
        end, explicit = add_months(start, filters.months), True
    else:
        end, explicit = start + timedelta(days=1), False
    if end <= start:
        raise FilterError("退租日期必须晚于入住日期")
    if (end - start).days > MAX_STAY_DAYS:
        raise FilterError("租期过长")
    return StayWindow(start, end, explicit)


def _distance_expr() -> str:
    return (
        f"({EARTH_RADIUS_KM} * 2 * asin(sqrt("
        "power(sin(radians(e.lat::float8 - %s) / 2), 2) + "
        "cos(radians(%s)) * cos(radians(e.lat::float8)) * power(sin(radians(e.lng::float8 - %s) / 2), 2))))"
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def compile_filters(filters: ListingFilters, today: date) -> CompiledQuery:
    clauses = ["l.status = 'published'", "d.status = 'active'"]
    params: list[Any] = []

    if filters.rent_type:
        clauses.append("l.rent_type = %s")
        params.append(filters.rent_type)
    if filters.keyword:
        like = f"%{_escape_like(filters.keyword.strip())}%"
        clauses.append(
            "(l.title ILIKE %s OR l.description ILIKE %s OR e.name ILIKE %s OR e.district ILIKE %s "
            "OR e.address ILIKE %s OR array_to_string(l.tags, ' ') ILIKE %s)"
        )
        params.extend([like] * 6)
    if filters.district:
        clauses.append("e.district = %s")
        params.append(filters.district)
    if filters.min_price is not None:
        clauses.append(f"{PRICE_EXPR} >= %s")
        params.append(filters.min_price)
    if filters.max_price is not None:
        clauses.append(f"{PRICE_EXPR} <= %s")
        params.append(filters.max_price)
    if filters.min_bedrooms is not None:
        clauses.append("l.bedrooms >= %s")
        params.append(filters.min_bedrooms)
    if filters.tags:
        clauses.append("l.tags @> %s::text[]")
        params.append(list(filters.tags))
    if filters.recommended is not None:
        clauses.append("l.recommended = %s")
        params.append(filters.recommended)
    if filters.exclude_id is not None:
        clauses.append("l.id <> %s")
        params.append(filters.exclude_id)
    if filters.bbox:
        b = filters.bbox
        clauses.append("e.lng BETWEEN %s AND %s AND e.lat BETWEEN %s AND %s")
        params.extend([b.min_lng, b.max_lng, b.min_lat, b.max_lat])

    stay = resolve_stay(filters, today)
    if stay:
        clauses.append("(l.available_from IS NULL OR l.available_from <= %s)")
        params.append(stay.start)
        clauses.append(
            "NOT EXISTS (SELECT 1 FROM listing_unavailability u WHERE u.listing_id = l.id "
            "AND u.start_date < %s AND u.end_date > %s)"
        )
        params.extend([stay.end, stay.start])
        if stay.explicit_length:
            clauses.append("((l.rent_type = 'short' AND l.min_nights <= %s) OR (l.rent_type <> 'short' AND l.min_months <= %s))")
            params.extend([stay.nights, max(stay.months, 1) if filters.months is None else filters.months])

    distance_select, distance_params = "", ()
    if filters.near:
        p = filters.near
        expr = _distance_expr()
        geo = (p.lat, p.lat, p.lng)
        distance_select, distance_params = f", {expr} AS distance_km", geo
        radius = filters.radius_km or DEFAULT_NEARBY_RADIUS_KM
        # 先用经纬度框粗筛走索引友好的比较，再精确算距离
        dlat = radius / 111.0
        clauses.append("e.lat BETWEEN %s AND %s")
        params.extend([p.lat - dlat, p.lat + dlat])
        clauses.append(f"{expr} <= %s")
        params.extend([*geo, radius])

    order = {
        "latest": "l.published_at DESC, l.id DESC",
        "price_asc": f"{PRICE_EXPR} ASC, l.id DESC",
        "price_desc": f"{PRICE_EXPR} DESC, l.id DESC",
        "distance": "distance_km ASC, l.id DESC" if filters.near else "l.published_at DESC, l.id DESC",
    }[filters.sort]

    return CompiledQuery(" AND ".join(clauses), tuple(params), order, distance_select, distance_params)
