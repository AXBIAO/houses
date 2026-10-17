"""/api/listings 查询参数（字典）⇄ ListingFilters。订阅保存的条件与 AI 解析结果都走这里，校验规则与列表接口一致。"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.app.domain.listing_search import FilterError, ListingFilters

ALLOWED_KEYS = frozenset({"type", "q", "district", "minPrice", "maxPrice", "bedrooms", "tags", "moveIn", "moveOut", "months"})
MAX_TAGS = 8


class QueryParams(BaseModel):
    type: Literal["long", "short", "shared"] | None = None
    q: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=30)
    minPrice: int | None = Field(None, ge=0, le=1_000_000)
    maxPrice: int | None = Field(None, ge=0, le=1_000_000)
    bedrooms: int | None = Field(None, ge=0, le=20)
    tags: str | None = Field(None, max_length=200)
    moveIn: date | None = None
    moveOut: date | None = None
    months: int | None = Field(None, ge=1, le=36)

    @field_validator("q", "district", "tags")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


def normalize(params: Mapping[str, Any]) -> dict[str, str]:
    """校验并规范化为字符串字典（去掉空值与未知键），用于入库保存。"""
    unknown = set(params) - ALLOWED_KEYS
    if unknown:
        raise FilterError(f"不支持的条件：{', '.join(sorted(unknown))}")
    try:
        parsed = QueryParams.model_validate({k: v for k, v in params.items() if v not in (None, "")})
    except ValidationError as exc:
        raise FilterError("筛选条件格式不正确") from exc
    if parsed.minPrice is not None and parsed.maxPrice is not None and parsed.minPrice > parsed.maxPrice:
        raise FilterError("最低价不能高于最高价")
    tags = _tags(parsed.tags)
    out = {k: str(v) for k, v in parsed.model_dump(exclude_none=True).items() if k != "tags"}
    if tags:
        out["tags"] = ",".join(tags)
    return out


def _tags(raw: str | None) -> tuple[str, ...]:
    tags = tuple(dict.fromkeys(t.strip() for t in (raw or "").split(",") if t.strip()))
    if len(tags) > MAX_TAGS or any(len(t) > 20 for t in tags):
        raise FilterError("标签过多或过长")
    return tags


def to_filters(params: Mapping[str, str], today: date) -> ListingFilters:
    """订阅里保存的入住日期过期后不再限制（否则旧订阅会一直匹配失败）。"""
    p = QueryParams.model_validate(params)
    move_in = p.moveIn if p.moveIn and p.moveIn >= today else None
    move_out = p.moveOut if move_in and p.moveOut and p.moveOut > move_in else None
    return ListingFilters(
        rent_type=p.type, keyword=p.q, district=p.district, min_price=p.minPrice, max_price=p.maxPrice,
        min_bedrooms=p.bedrooms, tags=_tags(p.tags), move_in=move_in, move_out=move_out, months=p.months,
    )
