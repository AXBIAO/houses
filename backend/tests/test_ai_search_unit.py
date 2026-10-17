from __future__ import annotations

from datetime import date

import pytest

from backend.app.domain.ai_search import ParsedQuery, Vocabulary, cn_number, describe, match_reasons, parse_rules

TODAY = date(2026, 10, 17)
VOCAB = Vocabulary(
    districts=("高新区", "锦江区", "武侯区", "青羊区"),
    tags=("近地铁", "押一付一", "拎包入住", "可养宠物", "独卫", "电梯房", "江景"),
    communities=("天府软件园公寓", "春熙公馆"),
)


def parse(text: str) -> ParsedQuery:
    return parse_rules(text, VOCAB, TODAY)


@pytest.mark.parametrize(("text", "value"), [("3", 3), ("两", 2), ("十", 10), ("十二", 12), ("二十", 20), ("二十四", 24), ("x", None)])
def test_cn_number(text, value):
    assert cn_number(text) == value


def test_typical_long_term_request():
    q = parse("想在高新区租个两室，预算5000以内，最好近地铁能养宠物，租一年")
    assert q.to_query() == {
        "type": "long", "district": "高新区", "maxPrice": "5000", "bedrooms": "2",
        "tags": "近地铁,可养宠物", "months": "12",
    }


@pytest.mark.parametrize(("text", "low", "high"), [
    ("3000-5000", 3000, 5000), ("3k到5k", 3000, 5000), ("4000左右", 3200, 4800),
    ("不超过4500元", None, 4500), ("预算3千", None, 3000), ("2000以上", 2000, None), ("1万以内", None, 10000),
])
def test_price_forms(text, low, high):
    q = parse(f"锦江 {text} 的房子")
    assert (q.min_price, q.max_price) == (low, high)


def test_numbers_for_rooms_and_months_are_not_read_as_price():
    q = parse("3室 租6个月")
    assert (q.bedrooms, q.months, q.min_price, q.max_price) == (3, 6, None, None)


def test_short_stay_with_dates_and_nights():
    q = parse("11月1日到11月3日 春熙路附近短租 每晚300以内")
    assert q.rent_type == "short"
    assert (q.move_in, q.move_out) == (date(2026, 11, 1), date(2026, 11, 3))
    assert q.max_price == 300 and q.near_me
    assert q.to_query()["moveOut"] == "2026-11-03"

    q2 = parse("10月20号入住，住3晚，民宿")
    assert (q2.move_in, q2.move_out) == (date(2026, 10, 20), date(2026, 10, 23))


def test_past_date_rolls_to_next_year():
    assert parse("3月1日入住").move_in == date(2027, 3, 1)


def test_shared_and_relative_dates():
    q = parse("找个合租单间 下个月入住 独立卫生间")
    assert q.rent_type == "shared" and q.move_in == date(2026, 11, 1) and q.tags == ("独卫",)
    assert parse("马上就能住的整租").move_in == TODAY


def test_short_district_name_and_community():
    q = parse("锦江那边，春熙公馆有没有")
    assert q.district == "锦江区" and q.keyword == "春熙公馆"


def test_unknown_tags_are_ignored():
    q = parse_rules("要车位和电梯", Vocabulary(tags=("电梯房",)), TODAY)
    assert q.tags == ("电梯房",)  # 车位不在库里，不生成搜不到的条件


def test_empty_query():
    assert parse("帮我找找房子").is_empty()


def test_merge_prefers_primary_and_unions_tags():
    primary = ParsedQuery(rent_type="long", tags=("近地铁",))
    fallback = ParsedQuery(rent_type="short", max_price=5000, tags=("独卫",))
    merged = primary.merged_with(fallback)
    assert (merged.rent_type, merged.max_price, merged.tags) == ("long", 5000, ("近地铁", "独卫"))


def test_describe_and_reasons():
    q = parse("高新区两室5000以内近地铁")
    labels = [c["label"] for c in describe(q)]
    assert labels == ["高新区", "¥5000/月以内", "2 室起", "近地铁"]
    reasons = match_reasons({"price": 4200, "district": "高新区", "bedrooms": 2, "tags": ["近地铁", "电梯房"]}, q)
    assert reasons == ["¥4200 在预算内", "位于高新区", "2 室", "近地铁"]
