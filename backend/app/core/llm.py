"""AI 找房的大模型解析（OpenAI 兼容 /chat/completions）。任何失败都返回 None，由规则解析兜底。"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from backend.app.domain.ai_search import ParsedQuery, Vocabulary
from backend.app.services.runtime_config import LlmConfig

logger = logging.getLogger("houses.llm")

SYSTEM_PROMPT = """你是租房搜索助手。把用户的一句话需求转换成 JSON 筛选条件，只输出 JSON，不要解释。
字段（都可省略，不确定就不要填）：
- rentType: "long"(长租/整租) | "short"(短租/日租/民宿) | "shared"(合租/单间)
- minPrice, maxPrice: 整数，长租合租为月租，短租为每晚价格
- bedrooms: 整数，最少几室
- district: 只能从这些区域里选：{districts}
- tags: 数组，只能从这些标签里选：{tags}
- community: 小区名，只能从这些里选：{communities}
- months: 整数 1-36，租多久
- moveIn, moveOut: YYYY-MM-DD，今天是 {today}；只给月日时取今天之后最近的日期
- nearMe: 布尔，用户是否要求离自己近"""


class LlmFilters(BaseModel):
    rentType: Literal["long", "short", "shared"] | None = None
    minPrice: int | None = Field(None, ge=0, le=1_000_000)
    maxPrice: int | None = Field(None, ge=0, le=1_000_000)
    bedrooms: int | None = Field(None, ge=0, le=10)
    district: str | None = None
    tags: list[str] = Field(default_factory=list)
    community: str | None = None
    months: int | None = Field(None, ge=1, le=36)
    moveIn: date | None = None
    moveOut: date | None = None
    nearMe: bool = False


def _extract_json(content: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def to_parsed(raw: dict[str, Any], vocab: Vocabulary, today: date) -> ParsedQuery | None:
    """校验并收敛到词表：模型给出的区域、标签、小区不在库里就丢弃，日期不能早于今天。"""
    try:
        f = LlmFilters.model_validate(raw)
    except ValidationError:
        return None
    min_price, max_price = f.minPrice, f.maxPrice
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price
    move_in = f.moveIn if f.moveIn and f.moveIn >= today else None
    move_out = f.moveOut if f.moveOut and move_in and f.moveOut > move_in else None
    return ParsedQuery(
        rent_type=f.rentType, min_price=min_price, max_price=max_price, bedrooms=f.bedrooms,
        district=f.district if f.district in vocab.districts else None,
        tags=tuple(dict.fromkeys(t for t in f.tags if t in vocab.tags))[:8],
        keyword=f.community if f.community in vocab.communities else None,
        months=f.months, move_in=move_in, move_out=move_out, near_me=f.nearMe,
    )


class LlmError(Exception):
    pass


async def _complete(config: LlmConfig, system: str, user: str) -> str:
    body = {"model": config.model, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    url = config.base_url.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            res = await client.post(url, json=body, headers={"Authorization": f"Bearer {config.api_key}"})
    except httpx.HTTPError as exc:
        raise LlmError(f"无法连接大模型服务：{type(exc).__name__}") from exc
    if res.status_code >= 400:
        raise LlmError(f"大模型服务返回 {res.status_code}：{res.text[:200]}")
    try:
        return res.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LlmError("大模型返回格式不是 OpenAI 兼容的 chat/completions") from exc


def _prompt(vocab: Vocabulary, today: date) -> str:
    return SYSTEM_PROMPT.format(
        districts="、".join(vocab.districts) or "（无）", tags="、".join(vocab.tags) or "（无）",
        communities="、".join(vocab.communities[:50]) or "（无）", today=today.isoformat(),
    )


async def parse_with_llm(query: str, vocab: Vocabulary, today: date, config: LlmConfig) -> ParsedQuery | None:
    """失败时返回 None，由规则解析兜底。"""
    if not config.enabled:
        return None
    try:
        content = await _complete(config, _prompt(vocab, today), query)
    except LlmError as exc:
        logger.warning("大模型解析失败，改用规则解析：%s", exc)
        return None
    raw = _extract_json(content)
    return to_parsed(raw, vocab, today) if raw else None


async def probe_llm(config: LlmConfig, vocab: Vocabulary, today: date, query: str) -> dict[str, Any]:
    """后台「测试连接」：返回成功与否、原因和解析样例，方便管理员排查。"""
    if not config.enabled:
        return {"ok": False, "message": "请先填写接口地址、API Key 与模型名称"}
    try:
        content = await _complete(config, _prompt(vocab, today), query)
    except LlmError as exc:
        return {"ok": False, "message": str(exc)}
    raw = _extract_json(content)
    if raw is None:
        return {"ok": False, "message": "模型有响应，但没有返回 JSON，换一个更听话的模型试试", "raw": content[:300]}
    parsed = to_parsed(raw, vocab, today)
    return {"ok": parsed is not None, "message": "连接正常" if parsed else "返回的 JSON 字段不合法", "filters": parsed.to_query() if parsed else raw}
