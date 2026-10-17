"""AI 一键找房与房源订阅推送。"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, timedelta

import httpx
import pytest
import redis

from backend.app.core import llm as llm_module
from backend.app.domain.ai_search import ParsedQuery, Vocabulary
from backend.app.services.notifier import NotificationHub

DISTRICT = "订阅测试区"
OTHER_DISTRICT = "订阅对照区"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client) -> tuple[str, dict[str, str]]:
    email = f"sub{uuid.uuid4().hex[:8]}@example.com"
    token = client.post("/api/auth/register", json={"email": email, "username": "订阅用户", "password": "Passw0rd!"}).json()["token"]
    return email, _auth(token)


@pytest.fixture(scope="module")
def admin(client):
    return _auth(client.post("/api/auth/login", json={"account": "root@example.com", "password": "Root@123456"}).json()["token"])


@pytest.fixture(scope="module")
def landlord(client, admin, request):
    email, h = _register(client)
    landlord_id = client.post("/api/admin/landlords", headers=admin, json={"name": "订阅房东", "ownerAccount": email}).json()["id"]
    estates = {}
    for district, name in ((DISTRICT, "订阅花园"), (OTHER_DISTRICT, "对照花园")):
        estates[district] = client.post("/api/landlord/estates", headers=h, json={
            "name": name, "city": "成都", "district": district, "lat": 30.6, "lng": 104.05}).json()["id"]
    request.addfinalizer(lambda: client.patch(f"/api/admin/landlords/{landlord_id}", headers=admin, json={"status": "disabled"}))
    return {"h": h, "estates": estates}


@pytest.fixture(autouse=True)
def clear_ai_limit():
    r = redis.Redis(host="localhost", port=int(os.environ["REDIS_PORT"]), db=15)
    for key in r.scan_iter("houses:ai:*"):
        r.delete(key)


def _listing(client, landlord, *, district=DISTRICT, publish=True, **overrides) -> int:
    body = {"estateId": landlord["estates"][district], "rentType": "long", "title": "订阅测试两居", "area": 70,
            "priceMonth": 4200, "bedrooms": 2, "halls": 1, "tags": ["近地铁"]}
    body.update(overrides)
    listing_id = client.post("/api/landlord/listings", headers=landlord["h"], json=body).json()["id"]
    if publish:
        assert client.post(f"/api/landlord/listings/{listing_id}/status", headers=landlord["h"], json={"status": "published"}).status_code == 200
    return listing_id


def _notifications(client, h):
    return client.get("/api/notifications", headers=h).json()


# ---- AI 找房 -------------------------------------------------------------

def test_ai_search_with_rules(client, landlord):
    listing = _listing(client, landlord)
    res = client.post("/api/ai/search", json={"query": f"{DISTRICT}两室，5000以内，近地铁，租一年"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "rules" and body["understood"] and body["relaxed"] == []
    assert body["filters"] == {"type": "long", "district": DISTRICT, "maxPrice": "5000", "bedrooms": "2", "tags": "近地铁", "months": "12"}
    hit = next(i for i in body["items"] if i["id"] == listing)
    assert hit["reasons"][:2] == ["¥4200 在预算内", f"位于{DISTRICT}"]


def test_ai_search_relaxes_when_nothing_matches(client, landlord):
    _listing(client, landlord)
    body = client.post("/api/ai/search", json={"query": f"{DISTRICT}五室 近地铁"}).json()
    # 只放宽真正卡住的居室，「近地铁」这一要求保留
    assert body["relaxed"] == ["居室"] and body["total"] >= 1
    assert body["filters"]["tags"] == "近地铁"
    # 单项放宽都不够时叠加放宽，并如实返回仍然没有结果
    stacked = client.post("/api/ai/search", json={"query": f"{DISTRICT}五室 1000以内"}).json()
    assert stacked["relaxed"] == ["居室", "预算上浮 20%"] and stacked["total"] == 0


def test_ai_search_asks_for_location(client):
    body = client.post("/api/ai/search", json={"query": "附近的房子"}).json()
    assert body["needLocation"] is True


def test_ai_search_uses_llm_and_merges_rules(client, landlord, monkeypatch):
    async def fake_llm(query, vocab, today, config):
        assert DISTRICT in vocab.districts
        return ParsedQuery(rent_type="long", district=DISTRICT)

    monkeypatch.setattr("backend.app.api.routes_ai.parse_with_llm", fake_llm)
    body = client.post("/api/ai/search", json={"query": "预算5000以内"}).json()
    assert body["source"] == "llm"
    assert body["filters"] == {"type": "long", "district": DISTRICT, "maxPrice": "5000"}


def test_ai_search_validation_and_rate_limit(client):
    assert client.post("/api/ai/search", json={"query": ""}).status_code == 422
    assert client.post("/api/ai/search", json={"query": "x" * 201}).status_code == 422
    redis.Redis(host="localhost", port=int(os.environ["REDIS_PORT"]), db=15).set("houses:ai:testclient", 30)
    assert client.post("/api/ai/search", json={"query": "两室"}).status_code == 429


def test_llm_output_is_constrained_to_vocabulary():
    today = date(2026, 10, 17)
    vocab = Vocabulary(districts=("高新区",), tags=("近地铁",), communities=("春熙公馆",))
    parsed = llm_module.to_parsed({
        "rentType": "long", "minPrice": 6000, "maxPrice": 3000, "district": "不存在区", "tags": ["近地铁", "游泳池"],
        "community": "春熙公馆", "moveIn": "2026-01-01", "months": 12,
    }, vocab, today)
    assert (parsed.min_price, parsed.max_price) == (3000, 6000)
    assert parsed.district is None and parsed.tags == ("近地铁",) and parsed.keyword == "春熙公馆"
    assert parsed.move_in is None and parsed.months == 12
    assert llm_module.to_parsed({"rentType": "villa"}, vocab, today) is None


def test_parse_with_llm_http(monkeypatch):
    from backend.app.services.runtime_config import LlmConfig

    config = LlmConfig(base_url="https://llm.example/v1", api_key="k", model="m")
    vocab = Vocabulary(districts=("高新区",))
    replies = iter([
        httpx.Response(200, json={"choices": [{"message": {"content": '```json\n{"district": "高新区", "bedrooms": 2}\n```'}}]}),
        httpx.Response(500, text="boom"),
    ])
    real_client = httpx.AsyncClient
    monkeypatch.setattr(llm_module.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(lambda req: next(replies)), **kw))
    ok = asyncio.run(llm_module.parse_with_llm("高新两室", vocab, date(2026, 10, 17), config))
    assert ok is not None and (ok.district, ok.bedrooms) == ("高新区", 2)
    assert asyncio.run(llm_module.parse_with_llm("高新两室", vocab, date(2026, 10, 17), config)) is None
    assert asyncio.run(llm_module.parse_with_llm("高新两室", vocab, date(2026, 10, 17), LlmConfig())) is None


# ---- 订阅 ----------------------------------------------------------------

def test_subscription_crud_and_limits(client):
    _, h = _register(client)
    _, other = _register(client)
    assert client.get("/api/subscriptions").status_code == 401
    assert client.post("/api/subscriptions", headers=h, json={"name": "空条件", "filters": {}}).status_code == 422
    assert client.post("/api/subscriptions", headers=h, json={"name": "x", "filters": {"foo": "1"}}).status_code == 422
    assert client.post("/api/subscriptions", headers=h, json={"name": "x", "filters": {"minPrice": 9, "maxPrice": 1}}).status_code == 422
    created = client.post("/api/subscriptions", headers=h, json={"name": " 高新两室 ", "filters": {"district": DISTRICT, "maxPrice": 5000, "q": " "}})
    assert created.status_code == 201, created.text
    sub = created.json()
    assert sub["name"] == "高新两室" and sub["filters"] == {"district": DISTRICT, "maxPrice": "5000"}
    assert "matchCount" in sub
    body = {"name": "改名", "filters": {"district": DISTRICT}, "emailEnabled": True, "active": False}
    assert client.put(f"/api/subscriptions/{sub['id']}", headers=other, json=body).status_code == 404
    assert client.delete(f"/api/subscriptions/{sub['id']}", headers=other).status_code == 404
    updated = client.put(f"/api/subscriptions/{sub['id']}", headers=h, json=body).json()
    assert (updated["name"], updated["active"], updated["emailEnabled"]) == ("改名", False, True)
    for i in range(9):
        assert client.post("/api/subscriptions", headers=h, json={"name": f"s{i}", "filters": {"bedrooms": 1}}).status_code == 201
    assert client.post("/api/subscriptions", headers=h, json={"name": "第11个", "filters": {"bedrooms": 1}}).status_code == 409
    assert client.delete(f"/api/subscriptions/{sub['id']}", headers=h).status_code == 204


def test_publish_and_price_drop_notify_once(client, landlord):
    _, h = _register(client)
    sub = client.post("/api/subscriptions", headers=h, json={"name": "测试区长租", "filters": {"district": DISTRICT, "type": "long"}}).json()
    _, idle = _register(client)
    paused = client.post("/api/subscriptions", headers=idle, json={"name": "暂停的", "filters": {"district": DISTRICT}}).json()
    client.put(f"/api/subscriptions/{paused['id']}", headers=idle, json={"name": "暂停的", "filters": {"district": DISTRICT}, "active": False})

    listing = _listing(client, landlord, title="新上架的湖景房")
    _listing(client, landlord, district=OTHER_DISTRICT)  # 不匹配的区域
    inbox = _notifications(client, h)
    assert inbox["unread"] == 1
    note = inbox["items"][0]
    assert note["kind"] == "new" and note["listingId"] == listing and note["subscriptionName"] == "测试区长租"
    assert note["title"] == "新房源：新上架的湖景房"
    assert _notifications(client, idle)["total"] == 0

    lh = landlord["h"]
    client.post(f"/api/landlord/listings/{listing}/status", headers=lh, json={"status": "offline"})
    client.post(f"/api/landlord/listings/{listing}/status", headers=lh, json={"status": "published"})
    assert _notifications(client, h)["total"] == 1  # 重新上架不重复通知

    detail = client.get(f"/api/landlord/listings/{listing}", headers=lh).json()
    edit = {k: detail[k] for k in ("estateId", "rentType", "title", "area", "bedrooms", "halls", "tags")}
    client.put(f"/api/landlord/listings/{listing}", headers=lh, json={**edit, "priceMonth": 4500})  # 涨价不通知
    assert _notifications(client, h)["total"] == 1
    client.put(f"/api/landlord/listings/{listing}", headers=lh, json={**edit, "priceMonth": 3900})
    inbox = _notifications(client, h)
    assert inbox["total"] == 2 and inbox["items"][0]["kind"] == "price_drop"
    assert inbox["items"][0]["body"].startswith("¥4500 → ¥3900/月")

    first = inbox["items"][1]["id"]
    assert client.post("/api/notifications/read", headers=h, json={"ids": [first]}).json() == {"updated": 1}
    assert _notifications(client, h)["unread"] == 1
    assert client.post("/api/notifications/read", headers=h, json={}).json() == {"updated": 1}
    assert client.get("/api/notifications", headers=h, params={"unread": "true"}).json()["total"] == 0
    assert sub["id"]


def test_compensation_job_does_not_duplicate(client, landlord):
    from backend.app.services.notifier import match_recent

    _, h = _register(client)
    client.post("/api/subscriptions", headers=h, json={"name": "补偿", "filters": {"district": DISTRICT, "bedrooms": 4}})
    _listing(client, landlord, bedrooms=4, title="四居")
    assert _notifications(client, h)["total"] == 1
    # 必须在应用自己的事件循环里执行：Redis 连接绑定在该循环上，换个循环跑会污染连接池
    client.portal.call(match_recent, client.app.state, 30)
    assert _notifications(client, h)["total"] == 1


def test_email_sent_when_enabled(client, landlord, monkeypatch, sql):
    sent = []

    async def fake_send(to, subject, text, config):
        sent.append((to, subject, text))
        return True

    monkeypatch.setattr("backend.app.services.notifier.send_mail", fake_send)
    email, h = _register(client)
    client.post("/api/subscriptions", headers=h, json={"name": "邮件", "filters": {"district": DISTRICT, "bedrooms": 3}, "emailEnabled": True})
    listing = _listing(client, landlord, bedrooms=3, title="三居邮件房")
    assert sent and sent[0][0] == email and "三居邮件房" in sent[0][1] and f"/listings/{listing}" in sent[0][2]
    note_id = _notifications(client, h)["items"][0]["id"]
    assert sql("SELECT emailed_at IS NOT NULL FROM notifications WHERE id = %s", (note_id,)) == [(True,)]


def test_stream_requires_login(client):
    assert client.get("/api/notifications/stream").status_code == 401


def test_local_hub_delivers_to_the_right_user():
    async def scenario():
        hub = NotificationHub(None)
        mine, theirs = hub.stream(1), hub.stream(2)
        first = asyncio.ensure_future(mine.__anext__())
        other = asyncio.ensure_future(theirs.__anext__())
        await asyncio.sleep(0)
        await hub.publish(1, {"title": "你好"})
        got = await asyncio.wait_for(first, 1)
        assert '"你好"' in got and not other.done()
        other.cancel()
        await asyncio.gather(other, return_exceptions=True)
        await mine.aclose()
        await theirs.aclose()

    asyncio.run(scenario())


def test_subscription_dates_expire_gracefully():
    from backend.app.domain.query_filters import to_filters

    past = (date.today() - timedelta(days=3)).isoformat()
    filters = to_filters({"moveIn": past, "months": "6", "district": DISTRICT}, date.today())
    assert filters.move_in is None and filters.months == 6
