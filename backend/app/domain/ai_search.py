"""AI 一键找房的规则解析（纯函数）：一句话需求 → 与 /api/listings 相同的筛选参数。

大模型不可用时作为兜底，也用来补全大模型漏掉的数字条件。词表（区域、标签、小区）由调用方从库里传入，
解析结果只会落在这些已存在的值上，避免生成永远搜不到的条件。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta

from backend.app.domain.dates import add_months

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
NUM = r"[0-9一二两三四五六七八九十]+"

# 口语 → 库里的标签名；只有标签真实存在时才采用
TAG_SYNONYMS: dict[str, tuple[str, ...]] = {
    "近地铁": ("地铁", "地铁口", "近地铁", "地铁站"),
    "可养宠物": ("宠物", "养猫", "养狗", "可养宠物"),
    "独卫": ("独卫", "独立卫生间", "独立卫浴"),
    "电梯房": ("电梯",),
    "押一付一": ("押一付一",),
    "拎包入住": ("拎包", "家具家电齐全", "家电齐全"),
    "可做饭": ("做饭", "厨房", "可做饭"),
    "可停车": ("停车", "车位"),
    "车位": ("车位",),
    "月付": ("月付",),
    "江景": ("江景", "河景"),
    "落地窗": ("落地窗",),
    "阳台": ("阳台",),
    "智能门锁": ("智能锁", "密码锁", "智能门锁"),
    "女生合租": ("女生", "限女生"),
    "亲子": ("亲子", "带娃", "带孩子"),
}

SHORT_WORDS = ("短租", "日租", "民宿", "按天", "按晚", "住几天", "旅游", "出差")
SHARED_WORDS = ("合租", "单间", "室友", "主卧", "次卧")
LONG_WORDS = ("长租", "整租", "月租", "年租")


@dataclass(frozen=True)
class Vocabulary:
    districts: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    communities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedQuery:
    rent_type: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    bedrooms: int | None = None
    district: str | None = None
    tags: tuple[str, ...] = ()
    keyword: str | None = None
    months: int | None = None
    move_in: date | None = None
    move_out: date | None = None
    near_me: bool = False

    def is_empty(self) -> bool:
        return self.to_query() == {}

    def to_query(self) -> dict[str, str]:
        """与前端 searchQuery.toQuery、后端 /api/listings 参数完全一致。"""
        out: dict[str, str] = {}
        if self.rent_type:
            out["type"] = self.rent_type
        if self.keyword:
            out["q"] = self.keyword
        if self.district:
            out["district"] = self.district
        if self.min_price is not None:
            out["minPrice"] = str(self.min_price)
        if self.max_price is not None:
            out["maxPrice"] = str(self.max_price)
        if self.bedrooms is not None:
            out["bedrooms"] = str(self.bedrooms)
        if self.tags:
            out["tags"] = ",".join(self.tags)
        if self.move_in:
            out["moveIn"] = self.move_in.isoformat()
        if self.rent_type == "short" and self.move_out:
            out["moveOut"] = self.move_out.isoformat()
        if self.rent_type != "short" and self.months:
            out["months"] = str(self.months)
        return out

    def merged_with(self, fallback: "ParsedQuery") -> "ParsedQuery":
        """以自身为准，缺失的字段用 fallback 补齐；标签取并集。"""
        tags = tuple(dict.fromkeys((*self.tags, *fallback.tags)))
        return replace(
            self,
            rent_type=self.rent_type or fallback.rent_type,
            min_price=self.min_price if self.min_price is not None else fallback.min_price,
            max_price=self.max_price if self.max_price is not None else fallback.max_price,
            bedrooms=self.bedrooms if self.bedrooms is not None else fallback.bedrooms,
            district=self.district or fallback.district,
            tags=tags,
            keyword=self.keyword or fallback.keyword,
            months=self.months or fallback.months,
            move_in=self.move_in or fallback.move_in,
            move_out=self.move_out or fallback.move_out,
            near_me=self.near_me or fallback.near_me,
        )


def cn_number(text: str) -> int | None:
    """解析 0-99 的阿拉伯或中文数字（十二、二十、两）。"""
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        tens, _, ones = text.partition("十")
        high = CN_DIGITS.get(tens, 1) if tens else 1
        low = CN_DIGITS.get(ones, 0) if ones else 0
        return high * 10 + low
    if len(text) == 1 and text in CN_DIGITS:
        return CN_DIGITS[text]
    return None


def _money(number: str, unit: str | None) -> int:
    value = float(number)
    if unit in ("k", "K", "千"):
        value *= 1000
    elif unit == "万":
        value *= 10000
    return int(round(value))


def _take(pattern: str, text: str) -> tuple[re.Match[str] | None, str]:
    """匹配后把命中的片段从文本里挖掉，避免数字被后续规则重复解读。"""
    match = re.search(pattern, text)
    if not match:
        return None, text
    return match, text[: match.start()] + " " + text[match.end():]


def _parse_dates(text: str, today: date) -> tuple[date | None, date | None, str]:
    move_in = move_out = None
    rng, text = _take(rf"({NUM})月({NUM})[日号]?\s*(?:到|至|-|~)\s*(?:({NUM})月)?({NUM})[日号]", text)
    if rng:
        month1, day1 = cn_number(rng.group(1)), cn_number(rng.group(2))
        month2 = cn_number(rng.group(3)) if rng.group(3) else month1
        day2 = cn_number(rng.group(4))
        move_in, move_out = _future_date(today, month1, day1), _future_date(today, month2, day2)
        if move_in and move_out and move_out <= move_in:
            move_out = _future_date(today.replace(year=today.year + 1), month2, day2) if month2 and day2 else None
        return move_in, move_out, text
    single, text = _take(rf"({NUM})月({NUM})[日号]", text)
    if single:
        move_in = _future_date(today, cn_number(single.group(1)), cn_number(single.group(2)))
    elif re.search("下个?月", text):
        move_in = add_months(today.replace(day=1), 1)
        text = re.sub("下个?月", " ", text)
    elif re.search("马上|立即|随时|现在|尽快|这周", text):
        move_in = today
    return move_in, move_out, text


def _future_date(today: date, month: int | None, day: int | None) -> date | None:
    if not month or not day or not 1 <= month <= 12:
        return None
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        return None
    if candidate < today:
        try:
            candidate = date(today.year + 1, month, day)
        except ValueError:
            return None
    return candidate


def _parse_price(text: str) -> tuple[int | None, int | None, str]:
    unit = r"\s*([kK千万])?\s*(?:元|块)?"
    rng, text = _take(rf"(\d+(?:\.\d+)?){unit}\s*(?:-|~|到|至)\s*(\d+(?:\.\d+)?){unit}", text)
    if rng:
        low_unit = rng.group(2) or rng.group(4)
        low, high = _money(rng.group(1), low_unit), _money(rng.group(3), rng.group(4))
        return min(low, high), max(low, high), text
    upper, text = _take(rf"(?:不超过|不高于|低于|少于|最多|预算|最高|控制在)\s*(\d+(?:\.\d+)?){unit}(?:以内|以下|之内|内)?", text)
    if upper:
        return None, _money(upper.group(1), upper.group(2)), text
    upper, text = _take(rf"(\d+(?:\.\d+)?){unit}(?:以内|以下|之内|内|左右)", text)
    if upper:
        value = _money(upper.group(1), upper.group(2))
        return (int(value * 0.8), int(value * 1.2), text) if "左右" in upper.group(0) else (None, value, text)
    lower, text = _take(rf"(\d+(?:\.\d+)?){unit}以上", text)
    if lower:
        return _money(lower.group(1), lower.group(2)), None, text
    return None, None, text


def parse_rules(query: str, vocab: Vocabulary, today: date) -> ParsedQuery:
    text = query.strip()

    rent_type = None
    if any(w in text for w in SHORT_WORDS) or re.search(rf"住\s*{NUM}\s*[晚天]", text):
        rent_type = "short"
    elif any(w in text for w in SHARED_WORDS):
        rent_type = "shared"
    elif any(w in text for w in LONG_WORDS):
        rent_type = "long"

    move_in, move_out, text = _parse_dates(text, today)

    months = None
    term, text = _take(rf"(半年|({NUM})\s*年|({NUM})\s*个月)", text)
    if term:
        if term.group(1) == "半年":
            months = 6
        elif term.group(2):
            years = cn_number(term.group(2))
            months = years * 12 if years else None
        else:
            months = cn_number(term.group(3))
        if months is not None and not 1 <= months <= 36:
            months = None
        if months and rent_type is None:
            rent_type = "long"

    bedrooms = None
    rooms, text = _take(rf"({NUM})\s*(?:室|居|房)", text)
    if rooms:
        bedrooms = cn_number(rooms.group(1))
    elif re.search("开间|单身公寓|一居", text):
        bedrooms = 1
    if bedrooms is not None and not 0 <= bedrooms <= 10:
        bedrooms = None

    nights, text = _take(rf"住\s*({NUM})\s*[晚天]", text)
    if nights and move_in and not move_out:
        count = cn_number(nights.group(1))
        if count:
            move_out = move_in + timedelta(days=count)

    min_price, max_price, text = _parse_price(text)

    district = next((d for d in vocab.districts if d in text or _short(d) in text), None)
    community = next((c for c in vocab.communities if c and c in text), None)
    vocab_tags = set(vocab.tags)
    tags = tuple(tag for tag, words in TAG_SYNONYMS.items() if tag in vocab_tags and any(w in text for w in words))
    tags += tuple(t for t in vocab.tags if t not in tags and t in text)
    near_me = bool(re.search("附近|周边|离我近|我这边", text))

    return ParsedQuery(rent_type=rent_type, min_price=min_price, max_price=max_price, bedrooms=bedrooms,
                       district=district, tags=tags[:8], keyword=community, months=months,
                       move_in=move_in, move_out=move_out, near_me=near_me)


def _short(district: str) -> str:
    """「高新区」也能被「高新」命中；单字区名不做缩写，避免误伤。"""
    stem = district.rstrip("区县市")
    return stem if len(stem) >= 2 else district


def describe(parsed: ParsedQuery) -> list[dict[str, str]]:
    """给前端展示的条件标签：key 对应 /api/listings 参数，删掉标签即删掉该条件。"""
    labels = {"long": "长租", "short": "短租", "shared": "合租"}
    chips: list[dict[str, str]] = []
    if parsed.rent_type:
        chips.append({"key": "type", "label": labels[parsed.rent_type]})
    if parsed.district:
        chips.append({"key": "district", "label": parsed.district})
    if parsed.keyword:
        chips.append({"key": "q", "label": f"「{parsed.keyword}」"})
    unit = "/晚" if parsed.rent_type == "short" else "/月"
    if parsed.min_price is not None and parsed.max_price is not None:
        chips.append({"key": "price", "label": f"¥{parsed.min_price}–{parsed.max_price}{unit}"})
    elif parsed.max_price is not None:
        chips.append({"key": "price", "label": f"¥{parsed.max_price}{unit}以内"})
    elif parsed.min_price is not None:
        chips.append({"key": "price", "label": f"¥{parsed.min_price}{unit}以上"})
    if parsed.bedrooms is not None:
        chips.append({"key": "bedrooms", "label": f"{parsed.bedrooms} 室及以上" if parsed.bedrooms >= 3 else f"{parsed.bedrooms} 室起"})
    for tag in parsed.tags:
        chips.append({"key": f"tag:{tag}", "label": tag})
    if parsed.move_in:
        chips.append({"key": "moveIn", "label": f"{parsed.move_in.month}月{parsed.move_in.day}日入住"})
    if parsed.rent_type == "short" and parsed.move_out:
        chips.append({"key": "moveOut", "label": f"{parsed.move_out.month}月{parsed.move_out.day}日退房"})
    if parsed.rent_type != "short" and parsed.months:
        chips.append({"key": "months", "label": f"租 {parsed.months} 个月"})
    if parsed.near_me:
        chips.append({"key": "near", "label": "离我近"})
    return chips


def match_reasons(item: dict, parsed: ParsedQuery) -> list[str]:
    """解释每套房为什么被推荐（只说满足了的条件）。"""
    reasons: list[str] = []
    price = item.get("price")
    if parsed.max_price is not None and price is not None and price <= parsed.max_price:
        reasons.append(f"¥{price} 在预算内")
    if parsed.district and item.get("district") == parsed.district:
        reasons.append(f"位于{parsed.district}")
    if parsed.bedrooms is not None and (item.get("bedrooms") or 0) >= parsed.bedrooms:
        reasons.append(f"{item.get('bedrooms')} 室")
    hit = [t for t in parsed.tags if t in (item.get("tags") or [])]
    if hit:
        reasons.append("、".join(hit))
    if parsed.move_in:
        reasons.append("所选日期可入住")
    if item.get("distanceKm") is not None:
        reasons.append(f"距你约 {item['distanceKm']} km")
    return reasons
