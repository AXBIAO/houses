"""演示数据可重复导入：已绑定的演示房东账号和他们做过的业务数据不会让重跑失败，账号也不会丢。"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from backend.scripts.demo_data import CITIES
from backend.scripts.seed_demo import DEMO_LANDLORDS, seed

TOTAL = sum(city.count for city in CITIES)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_reseed_keeps_member_accounts_and_clears_business_data(client, sql):
    assert seed() == TOTAL
    landlord_id = sql("SELECT id FROM landlords WHERE name = %s", (DEMO_LANDLORDS[0],))[0][0]
    email = f"demo{uuid.uuid4().hex[:6]}@example.com"
    res = client.post("/api/auth/register", json={"email": email, "username": "演示房东", "password": "Passw0rd!"})
    user_id, h = res.json()["user"]["id"], _auth(res.json()["token"])
    sql("INSERT INTO landlord_members (landlord_id, user_id, role) VALUES (%s, %s, 'owner')", (landlord_id, user_id))

    # 用演示账号做一笔完整业务：签约、登记收款
    listing = client.get("/api/landlord/listings", headers=h, params={"pageSize": 1}).json()["items"][0]["id"]
    end = (date.today() + timedelta(days=90)).isoformat()
    lease = client.post("/api/landlord/leases", headers=h, json={
        "listingId": listing, "newRenter": {"name": "演示租客", "phone": "13600000000"},
        "startDate": date.today().isoformat(), "endDate": end, "monthlyRent": "3000", "deposit": "1000", "payCycleMonths": 1})
    assert lease.status_code == 201, lease.text
    bill = lease.json()["bills"][0]["id"]
    assert client.post(f"/api/landlord/bills/{bill}/payments", headers=h, json={"amount": "1000", "method": "cash"}).status_code == 201

    assert seed() == TOTAL  # 重跑不因租约、账单、收款的外键而失败
    assert sql("SELECT count(*) FROM landlords WHERE name = ANY(%s)", (list(DEMO_LANDLORDS),)) == [(len(DEMO_LANDLORDS),)]
    assert sql("SELECT count(*) FROM listings l JOIN landlords d ON d.id = l.landlord_id WHERE d.name = ANY(%s)",
               (list(DEMO_LANDLORDS),)) == [(TOTAL,)]
    assert sql("SELECT count(*) FROM leases WHERE landlord_id = %s", (landlord_id,)) == [(0,)]
    me = client.get("/api/landlord/me", headers=h)
    assert me.status_code == 200 and me.json()["landlordId"] == landlord_id

    # 收尾：演示房东不影响其他模块对公开接口的精确断言
    sql("UPDATE landlords SET status = 'disabled' WHERE name = ANY(%s)", (list(DEMO_LANDLORDS),))


def test_seed_attaches_photos_and_sets_cover(sql, tmp_path):
    # 只放一张封面图：用到它的模板挂 1 张，其余模板缺图时跳过
    tiny_webp = bytes.fromhex("524946461a000000574542505650384c0d0000002f0000001007101111888888fe0700")
    (tmp_path / "living_modern.webp").write_bytes(tiny_webp)
    try:
        assert seed(photo_dir=tmp_path) == TOTAL
        rows = sql("SELECT l.cover_url, count(i.id) FROM listings l JOIN landlords d ON d.id = l.landlord_id "
                   "LEFT JOIN listing_images i ON i.listing_id = l.id WHERE d.name = ANY(%s) GROUP BY l.id, l.cover_url",
                   (list(DEMO_LANDLORDS),))
        with_photo = [r for r in rows if r[1]]
        assert with_photo and all(r[1] == 1 and r[0].startswith("/uploads/listings/") for r in with_photo)
        assert all(r[0] is None for r in rows if not r[1])
        cities = sql("SELECT DISTINCT e.city FROM estates e JOIN landlords d ON d.id = e.landlord_id WHERE d.name = ANY(%s)",
                     (list(DEMO_LANDLORDS),))
        assert {c[0] for c in cities} == {city.name for city in CITIES}
    finally:
        sql("UPDATE landlords SET status = 'disabled' WHERE name = ANY(%s)", (list(DEMO_LANDLORDS),))
