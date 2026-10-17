"""出租与收租（只记账）集成测试：签约出账、登记收款、减免、作废、抄表、退租结算、状态推进、房东隔离。"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.domain.dates import add_months

TODAY = date.today()


def iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _landlord(client, admin, name: str) -> dict:
    email = f"lease{uuid.uuid4().hex[:8]}@example.com"
    token = client.post("/api/auth/register", json={"email": email, "username": name, "password": "Passw0rd!"}).json()["token"]
    res = client.post("/api/admin/landlords", headers=admin, json={"name": name, "ownerAccount": email})
    assert res.status_code == 201, res.text
    return {"h": _auth(token), "id": res.json()["id"]}


def _listing(client, h) -> int:
    estate = client.post("/api/landlord/estates", headers=h, json={
        "name": "收租小区", "city": "成都", "district": "武侯区", "lat": 30.6, "lng": 104.0}).json()["id"]
    listing = client.post("/api/landlord/listings", headers=h, json={
        "estateId": estate, "rentType": "long", "title": "收租测试房", "area": 50, "priceMonth": 3000}).json()["id"]
    assert client.post(f"/api/landlord/listings/{listing}/status", headers=h, json={"status": "published"}).status_code == 200
    return listing


@pytest.fixture(scope="module")
def admin(client):
    token = client.post("/api/auth/login", json={"account": "root@example.com", "password": "Root@123456"}).json()["token"]
    return _auth(token)


@pytest.fixture(scope="module")
def env(client, admin, request):
    a, b = _landlord(client, admin, "收租房东甲"), _landlord(client, admin, "收租房东乙")
    fees = {}
    for name, kind, price, unit in [("管理费", "fixed", 50, ""), ("门卡", "one_time", 20, ""), ("电费", "metered", 1.2, "度")]:
        res = client.post("/api/landlord/fee-items", headers=a["h"], json={"name": name, "kind": kind, "defaultPrice": price, "unit": unit})
        assert res.status_code == 201, res.text
        fees[name] = res.json()["id"]

    def _hide():
        for landlord in (a, b):
            client.patch(f"/api/admin/landlords/{landlord['id']}", headers=admin, json={"status": "disabled"})

    request.addfinalizer(_hide)
    return {"a": a, "b": b, "fees": fees}


def _sign(client, env, listing, **overrides):
    body = {
        "listingId": listing, "newRenter": {"name": "张三", "phone": "13600000000", "idCardTail": "123x"},
        "startDate": iso(0), "endDate": (add_months(TODAY, 12) - timedelta(days=1)).isoformat(),
        "monthlyRent": "3000", "deposit": "3000", "payCycleMonths": 1,
        "fees": [{"feeItemId": env["fees"]["管理费"]}, {"feeItemId": env["fees"]["门卡"]}, {"feeItemId": env["fees"]["电费"], "price": "1.5"}],
    }
    body.update(overrides)
    return client.post("/api/landlord/leases", headers=env["a"]["h"], json=body)


def _bill(lease, kind="rent", period=1):
    return next(b for b in lease["bills"] if b["kind"] == kind and (kind != "rent" or b["periodNo"] == period))


def _pay(client, h, bill_id, amount, method="wechat"):
    return client.post(f"/api/landlord/bills/{bill_id}/payments", headers=h, json={"amount": str(amount), "method": method})


# ---- 签约 ----------------------------------------------------------------

def test_preview_matches_planner(client, env):
    listing = _listing(client, env["a"]["h"])
    res = client.post("/api/landlord/leases/preview", headers=env["a"]["h"], json={
        "listingId": listing, "renterId": None, "newRenter": {"name": "预览", "phone": "13600000001"},
        "startDate": "2026-11-01", "endDate": "2027-01-31", "monthlyRent": "3000", "deposit": "1000", "payCycleMonths": 1,
        "fees": [{"feeItemId": env["fees"]["管理费"]}, {"feeItemId": env["fees"]["门卡"]}]})
    assert res.status_code == 200, res.text
    bills = res.json()["bills"]
    assert [b["kind"] for b in bills] == ["deposit", "rent", "rent", "rent"]
    assert [b["totalAmount"] for b in bills] == [1000, 3070, 3050, 3050]


def test_sign_generates_bills_blocks_dates_and_unlists(client, env, sql):
    h = env["a"]["h"]
    listing = _listing(client, h)
    res = _sign(client, env, listing)
    assert res.status_code == 201, res.text
    lease = res.json()
    assert lease["status"] == "active" and lease["leaseNo"].startswith("HT")
    assert len([b for b in lease["bills"] if b["kind"] == "rent"]) == 12
    assert _bill(lease, "deposit")["totalAmount"] == 3000
    assert _bill(lease)["totalAmount"] == 3070  # 租金 + 管理费 + 一次性门卡
    assert {f["name"]: f["price"] for f in lease["fees"]}["电费"] == 1.5
    assert sql("SELECT status FROM listings WHERE id = %s", (listing,)) == [("offline",)]
    assert sql("SELECT kind, start_date FROM listing_unavailability WHERE listing_id = %s", (listing,)) == [("lease", TODAY)]
    assert sql("SELECT id_card_tail FROM renters WHERE id = %s", (lease["renterId"],)) == [("123X",)]


def test_overlap_and_expired_guards(client, env):
    h = env["a"]["h"]
    listing = _listing(client, h)
    assert _sign(client, env, listing, endDate=iso(30)).status_code == 201
    clash = _sign(client, env, listing, startDate=iso(20), endDate=iso(60))
    assert clash.status_code == 409 and "重叠" in clash.json()["detail"]
    later = _sign(client, env, listing, startDate=iso(31), endDate=iso(90))
    assert later.status_code == 201 and later.json()["status"] == "pending"


def test_expired_lease_must_check_out_first(client, env, sql):
    h = env["a"]["h"]
    listing = _listing(client, h)
    lease = _sign(client, env, listing, startDate=iso(0), endDate=iso(5), deposit="0").json()
    sql("UPDATE leases SET start_date = %s, end_date = %s WHERE id = %s", (TODAY - timedelta(days=40), TODAY - timedelta(days=1), lease["id"]))
    counts = client.app.state.leases.advance_statuses(TODAY)
    assert counts["expired"] >= 1
    assert client.get(f"/api/landlord/leases/{lease['id']}", headers=h).json()["status"] == "expired"
    res = _sign(client, env, listing, startDate=iso(10), endDate=iso(40))
    assert res.status_code == 409 and "退租" in res.json()["detail"]


def test_pending_becomes_active_on_start_date(client, env, sql):
    lease = _sign(client, env, _listing(client, env["a"]["h"]), startDate=iso(3), endDate=iso(60)).json()
    assert lease["status"] == "pending"
    client.app.state.leases.advance_statuses(TODAY)
    assert sql("SELECT status FROM leases WHERE id = %s", (lease["id"],)) == [("pending",)]
    client.app.state.leases.advance_statuses(TODAY + timedelta(days=3))
    assert sql("SELECT status FROM leases WHERE id = %s", (lease["id"],)) == [("active",)]


def test_sign_validation(client, env):
    listing = _listing(client, env["a"]["h"])
    assert _sign(client, env, listing, endDate=iso(-1)).status_code == 422
    assert _sign(client, env, listing, renterId=1).status_code == 422  # 已有租客与新租客只能二选一
    assert _sign(client, env, listing, payCycleMonths=0).status_code == 422
    bad_tail = _sign(client, env, listing, newRenter={"name": "李四", "phone": "13600000000", "idCardTail": "510104199001011234"})
    assert bad_tail.status_code == 422


# ---- 收款与减免（只记账）---------------------------------------------------

def test_record_payments_discount_and_void(client, env):
    h = env["a"]["h"]
    lease = _sign(client, env, _listing(client, h)).json()
    rent = _bill(lease)["id"]
    assert _pay(client, h, rent, 1000).json()["status"] == "partial"
    assert _pay(client, h, rent, 5000).status_code == 409
    assert _pay(client, h, rent, 100, method="deposit_offset").status_code == 422
    future = client.post(f"/api/landlord/bills/{rent}/payments", headers=h,
                         json={"amount": "1", "method": "cash", "paidOn": iso(1)})
    assert future.status_code == 422
    assert client.put(f"/api/landlord/bills/{rent}/discount", headers=h, json={"amount": "3000"}).status_code == 409
    detail = client.put(f"/api/landlord/bills/{rent}/discount", headers=h, json={"amount": "70", "note": "老客优惠"}).json()
    assert detail["outstanding"] == 2000 and detail["note"] == "老客优惠"
    settled = _pay(client, h, rent, 2000, method="cash").json()
    assert settled["status"] == "settled" and settled["settledAt"]
    payment = settled["payments"][0]["id"]
    assert client.post(f"/api/landlord/payments/{payment}/void", headers=h).status_code == 200
    after = client.get(f"/api/landlord/bills/{rent}", headers=h).json()
    assert after["status"] == "partial" and after["paidAmount"] == 2000
    assert client.post(f"/api/landlord/payments/{payment}/void", headers=h).status_code == 409


def test_void_lease_only_without_payments(client, env, sql):
    h = env["a"]["h"]
    listing = _listing(client, h)
    lease = _sign(client, env, listing).json()
    _pay(client, h, _bill(lease)["id"], 100)
    assert client.post(f"/api/landlord/leases/{lease['id']}/void", headers=h).status_code == 409

    clean = _sign(client, env, _listing(client, h)).json()
    voided = client.post(f"/api/landlord/leases/{clean['id']}/void", headers=h).json()
    assert voided["status"] == "void" and all(b["status"] == "void" for b in voided["bills"])
    assert sql("SELECT count(*) FROM listing_unavailability u JOIN leases l ON l.listing_id = u.listing_id "
               "WHERE l.id = %s", (clean["id"],)) == [(0,)]


# ---- 抄表 ----------------------------------------------------------------

def test_meter_readings_bill_into_next_open_rent_bill(client, env):
    h = env["a"]["h"]
    lease = _sign(client, env, _listing(client, h)).json()
    url = f"/api/landlord/leases/{lease['id']}/meter-readings"
    electric = env["fees"]["电费"]
    first = client.post(url, headers=h, json={"feeItemId": electric, "reading": "150", "readDate": iso(0)})
    assert first.status_code == 409 and "起始读数" in first.json()["detail"]
    created = client.post(url, headers=h, json={"feeItemId": electric, "reading": "150", "readDate": iso(0), "prevReading": "100"}).json()
    assert created["usage"] == 50 and created["amount"] == 75  # 租约约定单价 1.5
    first_rent = client.get(f"/api/landlord/bills/{created['billId']}", headers=h).json()
    assert first_rent["periodStart"] == iso(0) and first_rent["totalAmount"] == 3145
    second = client.post(url, headers=h, json={"feeItemId": electric, "reading": "180", "readDate": iso(0)}).json()
    assert second["usage"] == 30  # 上次读数自动带出
    assert client.post(url, headers=h, json={"feeItemId": electric, "reading": "200", "readDate": iso(-1)}).status_code == 409
    assert client.post(url, headers=h, json={"feeItemId": electric, "reading": "100", "readDate": iso(0)}).status_code == 409
    assert client.post(url, headers=h, json={"feeItemId": env["fees"]["管理费"], "reading": "1", "readDate": iso(0)}).status_code == 409
    assert client.delete(f"/api/landlord/meter-readings/{created['id']}", headers=h).status_code == 409
    assert client.delete(f"/api/landlord/meter-readings/{second['id']}", headers=h).status_code == 204
    assert client.get(f"/api/landlord/bills/{created['billId']}", headers=h).json()["totalAmount"] == 3145


# ---- 退租结算 ------------------------------------------------------------

def test_checkout_settlement(client, env, sql):
    """押金 5000：抵扣本期欠租和结算单，余额记为退押金负数流水；未来账单作废但挂着的电费不丢。"""
    h = env["a"]["h"]
    listing = _listing(client, h)
    start = add_months(TODAY, -1)
    lease = _sign(client, env, listing, startDate=start.isoformat(),
                  endDate=(add_months(start, 12) - timedelta(days=1)).isoformat(), deposit="5000").json()
    _pay(client, h, _bill(lease, "deposit")["id"], 5000)
    _pay(client, h, _bill(lease, period=1)["id"], 3070)
    # 今天抄表 → 记入「账期开始日 ≥ 今天」的最近一期（第 2 期从今天开始）
    reading = client.post(f"/api/landlord/leases/{lease['id']}/meter-readings", headers=h,
                          json={"feeItemId": env["fees"]["电费"], "reading": "40", "readDate": iso(0), "prevReading": "0"}).json()
    assert reading["amount"] == 60
    # 今天退租：第 2 期今天开始（不晚于退租日）保留，第 3 期起作废
    res = client.post(f"/api/landlord/leases/{lease['id']}/checkout", headers=h,
                      json={"checkoutDate": iso(0), "extras": [{"name": "保洁费", "amount": "100"}], "note": "提前退租"})
    assert res.status_code == 200, res.text
    result, after = res.json()["result"], res.json()["lease"]
    assert result["voidedBills"] == 10
    assert after["status"] == "checked_out"
    settlement = next(b for b in after["bills"] if b["kind"] == "settlement")
    assert settlement["totalAmount"] == 100  # 电费仍挂在保留的第 2 期上，结算单只有保洁费
    period2 = _bill(after, period=2)
    assert period2["status"] == "settled" and period2["totalAmount"] == 3110  # 3000 + 50 管理费 + 60 电费
    assert result["depositOffset"] == 3210 and result["depositRefund"] == 1790 and result["outstanding"] == 0
    deposit = _bill(after, "deposit")
    assert deposit["status"] == "settled"
    methods = sql("SELECT method, amount FROM payments p JOIN bills b ON b.id = p.bill_id WHERE b.lease_id = %s "
                  "AND p.method LIKE 'deposit%%' ORDER BY p.id", (lease["id"],))
    assert methods == [("deposit_offset", Decimal("3110.00")), ("deposit_offset", Decimal("100.00")),
                       ("deposit_refund", Decimal("-1790.00"))]
    assert sql("SELECT end_date FROM listing_unavailability WHERE listing_id = %s", (listing,)) == [(TODAY + timedelta(days=1),)]
    manual = sql("SELECT p.id FROM payments p JOIN bills b ON b.id = p.bill_id WHERE b.lease_id = %s AND p.method = 'wechat' LIMIT 1",
                 (lease["id"],))[0][0]
    assert client.post(f"/api/landlord/payments/{manual}/void", headers=h).status_code == 409
    assert client.post(f"/api/landlord/leases/{lease['id']}/checkout", headers=h, json={"checkoutDate": iso(0)}).status_code == 409


def test_checkout_keeps_meter_fee_when_future_bill_voided(client, env, sql):
    """回归：电费挂在未来账单上，退租作废该账单时必须先解绑，电费转入结算单。"""
    h = env["a"]["h"]
    lease = _sign(client, env, _listing(client, h), deposit="0").json()
    _pay(client, h, _bill(lease, period=1)["id"], 3070)
    # 已结清第 1 期，抄表费用会落到第 2 期（未来账单）
    reading = client.post(f"/api/landlord/leases/{lease['id']}/meter-readings", headers=h,
                          json={"feeItemId": env["fees"]["电费"], "reading": "20", "readDate": iso(0), "prevReading": "0"}).json()
    assert reading["billId"] == _bill(lease, period=2)["id"]
    after = client.post(f"/api/landlord/leases/{lease['id']}/checkout", headers=h, json={"checkoutDate": iso(0)}).json()["lease"]
    assert _bill(after, period=2)["status"] == "void"
    settlement = next(b for b in after["bills"] if b["kind"] == "settlement")
    assert settlement["totalAmount"] == 30 and settlement["status"] == "unpaid"
    assert sql("SELECT bill_id FROM meter_readings WHERE id = %s", (reading["id"],)) == [(settlement["id"],)]


def test_checkout_without_collected_deposit_voids_deposit_bill(client, env):
    h = env["a"]["h"]
    lease = _sign(client, env, _listing(client, h)).json()
    after = client.post(f"/api/landlord/leases/{lease['id']}/checkout", headers=h, json={"checkoutDate": iso(0)}).json()
    assert _bill(after["lease"], "deposit")["status"] == "void"
    assert after["result"]["depositRefund"] == 0
    assert after["result"]["outstanding"] == 3070  # 本期未收，退租后仍是欠款


# ---- 查询、删除保护 --------------------------------------------------------

def test_lists_summary_and_delete_guards(client, env):
    h = env["a"]["h"]
    lease = _sign(client, env, _listing(client, h), startDate=add_months(TODAY, -1).isoformat()).json()
    overdue = client.get("/api/landlord/bills", headers=h, params={"overdue": "true", "leaseId": lease["id"]}).json()
    assert {b["kind"] for b in overdue["items"]} == {"deposit", "rent"} and all(b["isOverdue"] for b in overdue["items"])
    summary = client.get("/api/landlord/bills/summary", headers=h).json()
    assert summary["overdueCount"] >= 2 and summary["overdueAmount"] > 0
    assert client.get("/api/landlord/leases", headers=h, params={"q": lease["leaseNo"]}).json()["total"] == 1
    assert client.delete(f"/api/landlord/renters/{lease['renterId']}", headers=h).status_code == 409
    assert client.delete(f"/api/landlord/fee-items/{env['fees']['管理费']}", headers=h).status_code == 409
    unused = client.post("/api/landlord/fee-items", headers=h, json={"name": "网费", "kind": "fixed", "defaultPrice": 30}).json()
    assert client.delete(f"/api/landlord/fee-items/{unused['id']}", headers=h).status_code == 204
    assert client.post("/api/landlord/fee-items", headers=h, json={"name": "管理费", "kind": "fixed", "defaultPrice": 1}).status_code == 409


# ---- 隔离 ----------------------------------------------------------------

def test_other_landlord_cannot_touch_leasing_data(client, env):
    a, b = env["a"]["h"], env["b"]["h"]
    listing = _listing(client, a)
    lease = _sign(client, env, listing).json()
    bill = _bill(lease)["id"]
    paid = _pay(client, a, bill, 10).json()["payments"][0]["id"]
    checks = [
        ("get", f"/api/landlord/leases/{lease['id']}", {}),
        ("patch", f"/api/landlord/leases/{lease['id']}", {"json": {"occupants": 2}}),
        ("post", f"/api/landlord/leases/{lease['id']}/void", {}),
        ("post", f"/api/landlord/leases/{lease['id']}/checkout", {"json": {"checkoutDate": iso(0)}}),
        ("post", f"/api/landlord/leases/{lease['id']}/meter-readings", {"json": {"feeItemId": env["fees"]["电费"], "reading": "1", "readDate": iso(0), "prevReading": "0"}}),
        ("get", f"/api/landlord/bills/{bill}", {}),
        ("post", f"/api/landlord/bills/{bill}/payments", {"json": {"amount": "1", "method": "cash"}}),
        ("put", f"/api/landlord/bills/{bill}/discount", {"json": {"amount": "1"}}),
        ("post", f"/api/landlord/payments/{paid}/void", {}),
        ("put", f"/api/landlord/renters/{lease['renterId']}", {"json": {"name": "x", "phone": "13600000009"}}),
        ("delete", f"/api/landlord/fee-items/{env['fees']['门卡']}", {}),
    ]
    for method, url, kwargs in checks:
        assert getattr(client, method)(url, headers=b, **kwargs).status_code == 404, (method, url)
    # 乙不能在甲的房源上签约，也不能用甲的租客或收费项目
    body = {"listingId": listing, "renterId": lease["renterId"], "startDate": iso(400), "endDate": iso(500),
            "monthlyRent": "1", "payCycleMonths": 1}
    assert client.post("/api/landlord/leases", headers=b, json=body).status_code == 404
    assert client.get("/api/landlord/bills", headers=b, params={"leaseId": lease["id"]}).json()["total"] == 0
    assert client.get("/api/landlord/payments", headers=b).json()["total"] == 0
