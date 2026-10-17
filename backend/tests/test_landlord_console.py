"""房东后台与平台管理。重点：房东之间的数据隔离、角色权限、停用即时生效。"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
TODAY = date.today()


def _iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user(client) -> tuple[str, str]:
    email = f"ll{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/auth/register", json={"email": email, "username": "房东测试", "password": "Passw0rd!"})
    assert res.status_code == 201, res.text
    return email, res.json()["token"]


@pytest.fixture(scope="module")
def admin(client) -> dict[str, str]:
    res = client.post("/api/auth/login", json={"account": "root@example.com", "password": "Root@123456"})
    assert res.status_code == 200
    return _auth(res.json()["token"])


@pytest.fixture(scope="module")
def ctx(client, admin, request):
    """两个房东 A / B，各有主账号；A 另有员工；外加一个普通用户。"""
    accounts = {}
    for key in ("ownerA", "ownerB", "staffA", "outsider"):
        email, token = _user(client)
        accounts[key] = {"email": email, "h": _auth(token)}
    for key, name in (("A", "甲房东"), ("B", "乙房东")):
        res = client.post("/api/admin/landlords", headers=admin,
                          json={"name": name, "contactPhone": "13800001111", "ownerAccount": accounts[f"owner{key}"]["email"]})
        assert res.status_code == 201, res.text
        accounts[f"landlord{key}"] = res.json()["id"]
    res = client.post("/api/landlord/members", headers=accounts["ownerA"]["h"],
                      json={"account": accounts["staffA"]["email"], "role": "staff"})
    assert res.status_code == 201, res.text

    def _hide_from_public():
        # 本模块上架的房源不能影响其他模块对公开接口的精确断言
        for key in ("landlordA", "landlordB"):
            client.patch(f"/api/admin/landlords/{accounts[key]}", headers=admin, json={"status": "disabled"})

    request.addfinalizer(_hide_from_public)
    return accounts


def _estate(client, headers, **overrides):
    body = {"name": "测试小区", "city": "成都", "district": "高新区", "address": "天府大道 1 号", "lat": 30.55, "lng": 104.06}
    body.update(overrides)
    res = client.post("/api/landlord/estates", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _listing(client, headers, estate_id, **overrides):
    body = {"estateId": estate_id, "rentType": "long", "title": "后台测试房源", "area": 60, "priceMonth": 3200,
            "bedrooms": 2, "halls": 1, "tags": ["近地铁", "近地铁", " 拎包入住 "]}
    body.update(overrides)
    res = client.post("/api/landlord/listings", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ---- 身份与权限 ----------------------------------------------------------

def test_requires_membership(client, ctx):
    assert client.get("/api/landlord/me").status_code == 401
    assert client.get("/api/landlord/me", headers=ctx["outsider"]["h"]).status_code == 403
    me = client.get("/api/landlord/me", headers=ctx["staffA"]["h"]).json()
    assert me == {"landlordId": ctx["landlordA"], "name": "甲房东", "role": "staff"}


def test_auth_me_reports_landlord(client, ctx):
    user = client.get("/api/auth/me", headers=ctx["ownerA"]["h"]).json()["user"]
    assert user["landlord"] == {"id": ctx["landlordA"], "name": "甲房东", "role": "owner", "active": True}
    assert client.get("/api/auth/me", headers=ctx["outsider"]["h"]).json()["user"]["landlord"] is None


def test_admin_endpoints_require_platform_role(client, ctx, admin):
    assert client.get("/api/admin/landlords", headers=ctx["ownerA"]["h"]).status_code == 403
    res = client.get("/api/admin/landlords", headers=admin, params={"q": "甲"})
    assert [r["name"] for r in res.json()["items"]] == ["甲房东"]
    assert res.json()["items"][0]["owners"] == ctx["ownerA"]["email"]


def test_create_landlord_conflicts(client, ctx, admin):
    taken = client.post("/api/admin/landlords", headers=admin, json={"name": "重复", "ownerAccount": ctx["staffA"]["email"]})
    assert taken.status_code == 409
    missing = client.post("/api/admin/landlords", headers=admin, json={"name": "无主", "ownerAccount": "nobody@example.com"})
    assert missing.status_code == 404
    bad_phone = client.post("/api/admin/landlords", headers=admin,
                            json={"name": "x", "contactPhone": "123", "ownerAccount": ctx["outsider"]["email"]})
    assert bad_phone.status_code == 422


# ---- 隔离 ----------------------------------------------------------------

def test_estates_are_isolated(client, ctx):
    a, b = ctx["ownerA"]["h"], ctx["ownerB"]["h"]
    estate = _estate(client, a, name="甲的小区")
    assert estate in [e["id"] for e in client.get("/api/landlord/estates", headers=a).json()["items"]]
    assert estate not in [e["id"] for e in client.get("/api/landlord/estates", headers=b).json()["items"]]
    body = {"name": "改名", "city": "成都", "district": "高新区", "lat": 30.5, "lng": 104}
    assert client.put(f"/api/landlord/estates/{estate}", headers=b, json=body).status_code == 404
    assert client.delete(f"/api/landlord/estates/{estate}", headers=b).status_code == 404
    # B 不能把房源挂到 A 的小区
    res = client.post("/api/landlord/listings", headers=b,
                      json={"estateId": estate, "rentType": "long", "title": "越权", "area": 30, "priceMonth": 1000})
    assert res.status_code == 404


def test_listings_are_isolated(client, ctx):
    a, b = ctx["ownerA"]["h"], ctx["ownerB"]["h"]
    listing = _listing(client, a, _estate(client, a))
    lid = listing["id"]
    assert listing["tags"] == ["近地铁", "拎包入住"]
    for method, url, kwargs in [
        ("get", f"/api/landlord/listings/{lid}", {}),
        ("put", f"/api/landlord/listings/{lid}", {"json": {"estateId": listing["estateId"], "rentType": "long", "title": "x", "area": 1, "priceMonth": 1}}),
        ("post", f"/api/landlord/listings/{lid}/status", {"json": {"status": "published"}}),
        ("delete", f"/api/landlord/listings/{lid}", {}),
        ("post", f"/api/landlord/listings/{lid}/blocks", {"json": {"start": _iso(1), "end": _iso(2)}}),
        ("post", f"/api/landlord/listings/{lid}/images", {"files": {"file": ("a.png", PNG, "image/png")}}),
    ]:
        assert getattr(client, method)(url, headers=b, **kwargs).status_code == 404, (method, url)
    assert lid not in [r["id"] for r in client.get("/api/landlord/listings", headers=b).json()["items"]]


# ---- 房源生命周期 --------------------------------------------------------

def test_listing_validation(client, ctx):
    a = ctx["ownerA"]["h"]
    estate = _estate(client, a)
    base = {"estateId": estate, "title": "校验", "area": 30}
    assert client.post("/api/landlord/listings", headers=a, json={**base, "rentType": "short", "priceMonth": 100}).status_code == 422
    assert client.post("/api/landlord/listings", headers=a, json={**base, "rentType": "long"}).status_code == 422
    assert client.post("/api/landlord/listings", headers=a,
                       json={**base, "rentType": "long", "priceMonth": 1, "floor": 9, "totalFloors": 3}).status_code == 422
    assert client.post("/api/landlord/listings", headers=a,
                       json={**base, "rentType": "long", "priceMonth": 1, "tags": [f"t{i}" for i in range(11)]}).status_code == 422


def test_publish_offline_delete(client, ctx):
    a = ctx["staffA"]["h"]  # 员工也能管理房源
    lid = _listing(client, a, _estate(client, a), title="生命周期房源")["id"]
    assert client.get(f"/api/listings/{lid}").status_code == 404  # 草稿不公开
    pub = client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "published"})
    assert pub.status_code == 200 and pub.json()["publishedAt"]
    assert client.get(f"/api/listings/{lid}").status_code == 200
    assert client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "published"}).status_code == 409
    assert client.delete(f"/api/landlord/listings/{lid}", headers=a).status_code == 409
    assert client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "offline"}).status_code == 200
    assert client.get(f"/api/listings/{lid}").status_code == 404
    assert client.delete(f"/api/landlord/listings/{lid}", headers=a).status_code == 204
    assert client.get(f"/api/landlord/listings/{lid}", headers=a).status_code == 404


def test_estate_delete_guard(client, ctx):
    a = ctx["ownerA"]["h"]
    estate = _estate(client, a)
    lid = _listing(client, a, estate)["id"]
    assert client.delete(f"/api/landlord/estates/{estate}", headers=a).status_code == 409
    assert client.delete(f"/api/landlord/listings/{lid}", headers=a).status_code == 204
    assert client.delete(f"/api/landlord/estates/{estate}", headers=a).status_code == 204


def test_images_upload_order_delete(client, ctx):
    a = ctx["ownerA"]["h"]
    lid = _listing(client, a, _estate(client, a))["id"]
    url = f"/api/landlord/listings/{lid}/images"
    first = client.post(url, headers=a, files={"file": ("a.png", PNG, "image/png")}).json()
    second = client.post(url, headers=a, files={"file": ("b.png", PNG, "image/png")}).json()
    assert client.post(url, headers=a, files={"file": ("x.png", b"not an image", "image/png")}).status_code == 422
    assert client.get(first["url"]).status_code == 200
    detail = client.get(f"/api/landlord/listings/{lid}", headers=a).json()
    assert detail["coverUrl"] == first["url"]
    detail = client.put(f"{url}/order", headers=a, json={"imageIds": [second["id"], first["id"]]}).json()
    assert detail["coverUrl"] == second["url"]
    assert client.put(f"{url}/order", headers=a, json={"imageIds": [second["id"]]}).status_code == 409
    assert client.delete(f"{url}/{second['id']}", headers=a).status_code == 204
    assert client.get(second["url"]).status_code == 404
    assert client.get(f"/api/landlord/listings/{lid}", headers=a).json()["coverUrl"] == first["url"]


def test_image_limit(client, ctx, monkeypatch):
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "listing_max_images", 1)
    a = ctx["ownerA"]["h"]
    lid = _listing(client, a, _estate(client, a))["id"]
    url = f"/api/landlord/listings/{lid}/images"
    assert client.post(url, headers=a, files={"file": ("a.png", PNG, "image/png")}).status_code == 201
    assert client.post(url, headers=a, files={"file": ("b.png", PNG, "image/png")}).status_code == 409


def test_blocks_affect_public_availability(client, ctx):
    a = ctx["ownerA"]["h"]
    lid = _listing(client, a, _estate(client, a), rentType="short", priceNight=199, priceMonth=None)["id"]
    client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "published"})
    window = {"type": "short", "moveIn": _iso(3), "moveOut": _iso(4), "pageSize": 50}
    ids = lambda: [i["id"] for i in client.get("/api/listings", params=window).json()["items"]]  # noqa: E731
    assert lid in ids()
    block = client.post(f"/api/landlord/listings/{lid}/blocks", headers=a, json={"start": _iso(2), "end": _iso(5), "note": "自住"})
    assert block.status_code == 201
    assert lid not in ids()
    assert client.post(f"/api/landlord/listings/{lid}/blocks", headers=a, json={"start": _iso(5), "end": _iso(2)}).status_code == 422
    assert client.delete(f"/api/landlord/listings/{lid}/blocks/{block.json()['id']}", headers=a).status_code == 204
    assert lid in ids()


# ---- 咨询 ----------------------------------------------------------------

def test_inquiries_scoped_and_updatable(client, ctx, sql):
    a, b = ctx["ownerA"]["h"], ctx["ownerB"]["h"]
    lid = _listing(client, a, _estate(client, a))["id"]
    client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "published"})
    sql("INSERT INTO listing_inquiries (listing_id, landlord_id, name, phone) VALUES (%s, %s, '访客', '13700000000')",
        (lid, ctx["landlordA"]))
    mine = client.get("/api/landlord/inquiries", headers=a, params={"status": "new"}).json()["items"]
    inquiry = next(i for i in mine if i["listingId"] == lid)
    assert inquiry["phone"] == "13700000000"
    assert all(i["listingId"] != lid for i in client.get("/api/landlord/inquiries", headers=b).json()["items"])
    assert client.patch(f"/api/landlord/inquiries/{inquiry['id']}", headers=b, json={"status": "closed"}).status_code == 404
    done = client.patch(f"/api/landlord/inquiries/{inquiry['id']}", headers=a, json={"status": "contacted", "note": "已约周六看房"}).json()
    assert done["status"] == "contacted" and done["note"] == "已约周六看房" and done["handledAt"]
    overview = client.get("/api/landlord/overview", headers=a).json()
    assert set(overview["listings"]) == {"draft", "published", "offline"}


# ---- 成员 ----------------------------------------------------------------

def test_member_management(client, ctx):
    owner, staff = ctx["ownerA"]["h"], ctx["staffA"]["h"]
    assert client.post("/api/landlord/members", headers=staff, json={"account": ctx["outsider"]["email"]}).status_code == 403
    assert client.post("/api/landlord/members", headers=owner, json={"account": ctx["ownerB"]["email"]}).status_code == 409
    assert client.post("/api/landlord/members", headers=owner, json={"account": "ghost@example.com"}).status_code == 404
    members = client.get("/api/landlord/members", headers=staff).json()["items"]
    owner_id = next(m["userId"] for m in members if m["role"] == "owner")
    assert client.delete(f"/api/landlord/members/{owner_id}", headers=owner).status_code == 409


# ---- 平台管控 ------------------------------------------------------------

def test_disable_landlord_takes_effect_immediately(client, ctx, admin):
    a = ctx["ownerB"]["h"]
    lid = _listing(client, a, _estate(client, a))["id"]
    client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "published"})
    assert client.get(f"/api/listings/{lid}").status_code == 200
    assert client.patch(f"/api/admin/landlords/{ctx['landlordB']}", headers=admin, json={"status": "disabled"}).status_code == 200
    assert client.get("/api/landlord/me", headers=a).status_code == 403
    assert client.get(f"/api/listings/{lid}").status_code == 404
    client.patch(f"/api/admin/landlords/{ctx['landlordB']}", headers=admin, json={"status": "active"})
    assert client.get(f"/api/listings/{lid}").status_code == 200


def test_admin_moderation(client, ctx, admin):
    a = ctx["ownerA"]["h"]
    lid = _listing(client, a, _estate(client, a))["id"]
    assert client.patch(f"/api/admin/listings/{lid}", headers=admin, json={"status": "offline"}).status_code == 409
    client.post(f"/api/landlord/listings/{lid}/status", headers=a, json={"status": "published"})
    assert client.patch(f"/api/admin/listings/{lid}", headers=admin, json={"recommended": True}).status_code == 200
    assert client.get(f"/api/listings/{lid}").json()["recommended"] is True
    assert client.patch(f"/api/admin/listings/{lid}", headers=admin, json={"status": "offline"}).status_code == 200
    assert client.get(f"/api/listings/{lid}").status_code == 404
    assert client.patch(f"/api/admin/listings/{lid}", headers=a, json={"status": "offline"}).status_code == 403
    listed = client.get("/api/admin/listings", headers=admin, params={"landlordId": ctx["landlordA"], "status": "offline"}).json()
    assert lid in [r["id"] for r in listed["items"]]
