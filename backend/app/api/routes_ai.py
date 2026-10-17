"""AI 一键找房：一句话 → 筛选条件 → 结果与匹配理由。没有结果时逐步放宽条件。"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.api.routes_listings import summary
from backend.app.core.llm import parse_with_llm
from backend.app.domain.ai_search import ParsedQuery, Vocabulary, describe, match_reasons, parse_rules
from backend.app.domain.listing_search import FilterError, GeoPoint
from backend.app.domain.query_filters import to_filters

router = APIRouter(prefix="/api/ai", tags=["ai"])

RESULT_SIZE = 12
NEAR_RADIUS_KM = 5.0
AI_LIMIT = 30
AI_WINDOW_SECONDS = 10 * 60

# 无结果时依次放宽：标签 → 入住日期与租期 → 居室 → 预算上浮 20%
RELAX_STEPS = (
    ("tags", "特色要求", lambda p: replace(p, tags=())),
    ("dates", "入住日期与租期", lambda p: replace(p, move_in=None, move_out=None, months=None)),
    ("bedrooms", "居室", lambda p: replace(p, bedrooms=None)),
    ("price", "预算上浮 20%", lambda p: replace(p, max_price=int(p.max_price * 1.2)) if p.max_price else p),
)


class AiSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)


async def _guard(request: Request) -> None:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return
    ip = request.client.host if request.client else "unknown"
    key = f"houses:ai:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, AI_WINDOW_SECONDS)
    if count > AI_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "AI 找房使用太频繁，请稍后再试")


async def _vocabulary(request: Request) -> Vocabulary:
    repo = request.app.state.listings
    facets, communities = await asyncio.gather(asyncio.to_thread(repo.facets), asyncio.to_thread(repo.communities))
    return Vocabulary(
        districts=tuple(d["value"] for d in facets["districts"]),
        tags=tuple(t["value"] for t in facets["tags"]),
        communities=tuple(communities),
    )


async def _search(request: Request, parsed: ParsedQuery, near: GeoPoint | None, today: date):
    filters = to_filters(parsed.to_query(), today)
    if near:
        filters = replace(filters, near=near, radius_km=NEAR_RADIUS_KM, sort="distance")
    return await asyncio.to_thread(request.app.state.listings.search, filters, today=today, limit=RESULT_SIZE, offset=0)


async def _search_with_relaxation(request: Request, parsed: ParsedQuery, near: GeoPoint | None, today: date):
    """无结果时先逐个尝试只放宽一项（尽量保留用户的其他要求），都不行再按顺序叠加放宽。"""
    rows, total = await _search(request, parsed, near, today)
    if total:
        return parsed, rows, total, []
    candidates = [(label, relax(parsed)) for _key, label, relax in RELAX_STEPS]
    candidates = [(label, looser) for label, looser in candidates if looser != parsed]
    for label, looser in candidates:
        rows, total = await _search(request, looser, near, today)
        if total:
            return looser, rows, total, [label]
    relaxed: list[str] = []
    current = parsed
    for label, relax in ((label, relax) for _key, label, relax in RELAX_STEPS):
        looser = relax(current)
        if looser == current:
            continue
        current = looser
        relaxed.append(label)
        rows, total = await _search(request, current, near, today)
        if total:
            break
    return current, rows, total, relaxed


@router.post("/search")
async def ai_search(body: AiSearchIn, request: Request) -> dict[str, Any]:
    await _guard(request)
    today = date.today()
    query = body.query.strip()
    vocab = await _vocabulary(request)
    rules = parse_rules(query, vocab, today)
    llm_config = await request.app.state.runtime.llm()
    llm = await parse_with_llm(query, vocab, today, llm_config)
    parsed, source = (llm.merged_with(rules), "llm") if llm is not None else (rules, "rules")
    near = GeoPoint(body.lat, body.lng) if parsed.near_me and body.lat is not None and body.lng is not None else None

    try:
        parsed, rows, total, relaxed = await _search_with_relaxation(request, parsed, near, today)
    except FilterError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    items = [summary(r) for r in rows]
    query_params = parsed.to_query()
    if near:
        query_params.update({"lat": str(body.lat), "lng": str(body.lng), "radiusKm": str(NEAR_RADIUS_KM), "sort": "distance"})
    return {
        "query": query,
        "source": source,
        "llmEnabled": llm_config.enabled,
        "understood": not parsed.is_empty() or near is not None,
        "needLocation": parsed.near_me and near is None,
        "conditions": describe(parsed),
        "filters": query_params,
        "relaxed": relaxed,
        "total": total,
        "items": [{**item, "reasons": match_reasons(item, parsed)} for item in items],
    }
