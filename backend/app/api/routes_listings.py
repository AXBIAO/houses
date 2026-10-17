"""公开找房接口：列表筛选、地图范围、首页聚合、详情、咨询。"""
from __future__ import annotations

import asyncio
import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.core.auth import OptionalUser, extract_user_id
from backend.app.domain.listing_search import BBox, FilterError, GeoPoint, ListingFilters

router = APIRouter(prefix="/api/listings", tags=["listings"])

PHONE_RE = re.compile(r"^1\d{10}$")
MAX_PAGE_SIZE = 50
MAX_MAP_SIZE = 300
MAX_TAGS = 8
INQUIRY_IP_LIMIT = 5
INQUIRY_IP_WINDOW_SECONDS = 10 * 60
INQUIRY_DUP_WINDOW_SECONDS = 60 * 60


def _repo(request: Request):
    return request.app.state.listings


def _num(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


def summary(row: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "title": row["title"],
        "rentType": row["rent_type"],
        "price": row["price"],
        "priceMonth": row["price_month"],
        "priceNight": row["price_night"],
        "bedrooms": row["bedrooms"],
        "halls": row["halls"],
        "baths": row["baths"],
        "area": _num(row["area"]),
        "floor": row["floor"],
        "tags": list(row["tags"] or []),
        "coverUrl": row["cover_url"],
        "recommended": row["recommended"],
        "availableFrom": row["available_from"],
        "publishedAt": row["published_at"],
        "estateId": row["estate_id"],
        "community": row["community"],
        "city": row["city"],
        "district": row["district"],
        "lat": _num(row["lat"]),
        "lng": _num(row["lng"]),
    }
    if "distance_km" in row:
        out["distanceKm"] = round(float(row["distance_km"]), 2)
    return out


def _parse_bbox(raw: str | None) -> BBox | None:
    if not raw:
        return None
    try:
        min_lng, min_lat, max_lng, max_lat = (float(x) for x in raw.split(","))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "bbox 格式应为 minLng,minLat,maxLng,maxLat") from exc
    if not (-180 <= min_lng < max_lng <= 180 and -90 <= min_lat < max_lat <= 90):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "bbox 范围无效")
    return BBox(min_lng, min_lat, max_lng, max_lat)


def _parse_tags(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    tags = tuple(dict.fromkeys(t.strip() for t in raw.split(",") if t.strip()))
    if len(tags) > MAX_TAGS or any(len(t) > 20 for t in tags):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "标签过多或过长")
    return tags


def build_filters(
    type: Literal["long", "short", "shared"] | None = None,
    q: str | None = Query(None, max_length=100),
    district: str | None = Query(None, max_length=30),
    minPrice: int | None = Query(None, ge=0, le=1_000_000),
    maxPrice: int | None = Query(None, ge=0, le=1_000_000),
    bedrooms: int | None = Query(None, ge=0, le=20),
    tags: str | None = Query(None, max_length=200),
    moveIn: date | None = None,
    moveOut: date | None = None,
    months: int | None = Query(None, ge=1, le=36),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    radiusKm: float | None = Query(None, gt=0, le=50),
    bbox: str | None = None,
    recommended: bool | None = None,
    sort: Literal["latest", "price_asc", "price_desc", "distance"] = "latest",
) -> ListingFilters:
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "lat 与 lng 需同时提供")
    if minPrice is not None and maxPrice is not None and minPrice > maxPrice:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "最低价不能高于最高价")
    return ListingFilters(
        rent_type=type,
        keyword=(q or "").strip() or None,
        district=(district or "").strip() or None,
        min_price=minPrice,
        max_price=maxPrice,
        min_bedrooms=bedrooms,
        tags=_parse_tags(tags),
        move_in=moveIn,
        move_out=moveOut,
        months=months,
        near=GeoPoint(lat, lng) if lat is not None and lng is not None else None,
        radius_km=radiusKm,
        bbox=_parse_bbox(bbox),
        recommended=recommended,
        sort=sort,
    )


async def _search(request: Request, filters: ListingFilters, limit: int, offset: int):
    try:
        return await asyncio.to_thread(_repo(request).search, filters, today=date.today(), limit=limit, offset=offset)
    except FilterError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("")
async def list_listings(
    request: Request,
    filters: ListingFilters = Depends(build_filters),
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> dict[str, Any]:
    rows, total = await _search(request, filters, pageSize, (page - 1) * pageSize)
    return {"items": [summary(r) for r in rows], "total": total, "page": page, "pageSize": pageSize}


@router.get("/map")
async def map_listings(
    request: Request,
    filters: ListingFilters = Depends(build_filters),
    limit: int = Query(200, ge=1, le=MAX_MAP_SIZE),
) -> dict[str, Any]:
    if filters.bbox is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "地图查询需要 bbox")
    rows, total = await _search(request, filters, limit, 0)
    return {"items": [summary(r) for r in rows], "total": total, "truncated": total > len(rows)}


@router.get("/home")
async def home_feed(request: Request) -> dict[str, Any]:
    feed = await asyncio.to_thread(_repo(request).home_feed, today=date.today(), limit=8)
    return {
        "today": [{**summary(r), "isToday": r["is_today"]} for r in feed["today"]],
        "recommended": [summary(r) for r in feed["recommended"]],
        "todayCount": feed["todayCount"],
    }


@router.get("/facets")
async def facets(request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_repo(request).facets)


def _mask_name(name: str) -> str:
    return name if len(name) <= 2 else f"{name[:2]}**"


@router.get("/{listing_id}")
async def listing_detail(listing_id: int, request: Request) -> dict[str, Any]:
    row = await asyncio.to_thread(_repo(request).get_public, listing_id, today=date.today())
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "房源不存在或已下架")
    return {
        **summary(row),
        "description": row["description"],
        "building": row["building"],
        "totalFloors": row["total_floors"],
        "orientation": row["orientation"],
        "depositMonths": row["deposit_months"],
        "minMonths": row["min_months"],
        "minNights": row["min_nights"],
        "address": row["address"],
        "landlordName": _mask_name(row["landlord_name"]),
        "images": row["images"],
        "unavailable": [{"start": r["start_date"], "end": r["end_date"]} for r in row["unavailable"]],
    }


class InquiryBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    phone: str
    message: str = Field("", max_length=500)
    moveIn: date | None = None
    moveOut: date | None = None

    @field_validator("name", "message")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError("手机号格式不正确")
        return value

    @model_validator(mode="after")
    def _dates(self) -> "InquiryBody":
        if not self.name:
            raise ValueError("请填写称呼")
        if self.moveIn and self.moveOut and self.moveOut <= self.moveIn:
            raise ValueError("退租日期必须晚于入住日期")
        return self


async def _guard_inquiry(request: Request, listing_id: int, phone: str) -> None:
    """同一 IP 10 分钟最多 5 条；同一手机号对同一房源 1 小时内只记一次。没有 Redis 时不限流。"""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return
    ip = request.client.host if request.client else "unknown"
    ip_key = f"houses:inquiry-ip:{ip}"
    count = await redis.incr(ip_key)
    if count == 1:
        await redis.expire(ip_key, INQUIRY_IP_WINDOW_SECONDS)
    if count > INQUIRY_IP_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "提交太频繁，请稍后再试")
    dup_key = f"houses:inquiry-dup:{listing_id}:{phone}"
    if not await redis.set(dup_key, "1", ex=INQUIRY_DUP_WINDOW_SECONDS, nx=True):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "已提交过咨询，房东会尽快联系你")


@router.post("/{listing_id}/inquiries", status_code=status.HTTP_201_CREATED)
async def create_inquiry(
    listing_id: int,
    body: InquiryBody,
    request: Request,
    identity: dict[str, Any] | None = Depends(OptionalUser),
) -> dict[str, Any]:
    repo = _repo(request)
    listing = await asyncio.to_thread(repo.get_public, listing_id, today=date.today())
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "房源不存在或已下架")
    await _guard_inquiry(request, listing_id, body.phone)
    row = await asyncio.to_thread(
        repo.create_inquiry,
        listing_id=listing_id,
        landlord_id=listing["landlord_id"],
        user_id=extract_user_id(identity),
        name=body.name,
        phone=body.phone,
        message=body.message,
        move_in=body.moveIn,
        move_out=body.moveOut,
        client_ip=request.client.host if request.client else None,
    )
    return {"id": row["id"], "createdAt": row["created_at"]}
