"""租约：签约一次出账、修改、作废、每日状态推进。退租结算见 checkout.py。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.billing import FixedFee, LeaseTerms, PlannedBill, plan_bills
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.ledger_ops import insert_bill
from backend.app.repositories.sql_helpers import like_pattern

OPEN_STATUSES = ("pending", "active", "expired")
EXPIRING_DAYS = 30

LIST_COLUMNS = """
    l.id, l.lease_no, l.listing_id, s.title AS listing_title, l.renter_id, r.name AS renter_name, r.phone AS renter_phone,
    l.start_date, l.end_date, l.monthly_rent, l.deposit, l.pay_cycle_months, l.status, l.checkout_date, l.created_at,
    coalesce(b.outstanding, 0) AS outstanding, coalesce(b.overdue, 0) AS overdue
"""
OUTSTANDING_JOIN = """
    LEFT JOIN LATERAL (
        SELECT sum(x.total_amount - x.discount_amount - x.paid_amount) AS outstanding,
               sum(x.total_amount - x.discount_amount - x.paid_amount) FILTER (WHERE x.due_date < %s) AS overdue
        FROM bills x WHERE x.lease_id = l.id AND x.status IN ('unpaid', 'partial')
    ) b ON TRUE
"""


@dataclass(frozen=True)
class FeeChoice:
    fee_item_id: int
    price: Decimal | None


@dataclass(frozen=True)
class SignInput:
    listing_id: int
    renter_id: int | None
    new_renter: dict[str, Any] | None
    start_date: date
    end_date: date
    monthly_rent: Decimal
    deposit: Decimal
    pay_cycle_months: int
    advance_days: int
    occupants: int
    signed_date: date | None
    fees: tuple[FeeChoice, ...]
    note: str
    inquiry_id: int | None


def resolve_fees(conn, landlord_id: int, choices: tuple[FeeChoice, ...]) -> list[dict[str, Any]]:
    """按房东自己的收费项目带出名称、计费方式与价格（可改价）。"""
    if not choices:
        return []
    ids = [c.fee_item_id for c in choices]
    if len(set(ids)) != len(ids):
        raise Conflict("收费项目重复")
    rows = {r["id"]: r for r in conn.execute(
        "SELECT id, name, kind, default_price, active FROM fee_items WHERE landlord_id = %s AND id = ANY(%s)",
        (landlord_id, ids),
    ).fetchall()}
    resolved = []
    for choice in choices:
        item = rows.get(choice.fee_item_id)
        if item is None:
            raise NotFound("收费项目不存在")
        if not item["active"]:
            raise Conflict(f"收费项目「{item['name']}」已停用")
        resolved.append({"fee_item_id": item["id"], "name": item["name"], "kind": item["kind"],
                         "price": choice.price if choice.price is not None else item["default_price"]})
    return resolved


def terms_for(data: SignInput, fees: list[dict[str, Any]]) -> LeaseTerms:
    fixed = tuple(FixedFee(f["fee_item_id"], f["name"], Decimal(f["price"]), f["kind"] == "one_time")
                  for f in fees if f["kind"] != "metered")
    return LeaseTerms(data.start_date, data.end_date, data.monthly_rent, data.deposit, data.pay_cycle_months,
                      data.advance_days, fixed)


def plan_or_conflict(terms: LeaseTerms) -> list[PlannedBill]:
    try:
        return plan_bills(terms)
    except ValueError as exc:
        raise Conflict(str(exc)) from exc


class LeaseRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    # ---- 签约 ----------------------------------------------------------

    def preview(self, landlord_id: int, data: SignInput) -> list[PlannedBill]:
        with self._db.transaction() as conn:
            return plan_or_conflict(terms_for(data, resolve_fees(conn, landlord_id, data.fees)))

    def sign(self, landlord_id: int, user_id: int, data: SignInput, *, today: date) -> int:
        with self._db.transaction() as conn:
            listing = conn.execute("SELECT id, status FROM listings WHERE id = %s AND landlord_id = %s FOR UPDATE",
                                   (data.listing_id, landlord_id)).fetchone()
            if listing is None:
                raise NotFound("房源不存在")
            self._check_overlap(conn, data)
            renter_id = self._renter(conn, landlord_id, data)
            fees = resolve_fees(conn, landlord_id, data.fees)
            bills = plan_or_conflict(terms_for(data, fees))
            status = "active" if data.start_date <= today else "pending"
            lease_id = conn.execute(
                "INSERT INTO leases (landlord_id, listing_id, renter_id, start_date, end_date, monthly_rent, deposit, "
                "pay_cycle_months, advance_days, occupants, signed_date, status, note, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (landlord_id, data.listing_id, renter_id, data.start_date, data.end_date, data.monthly_rent, data.deposit,
                 data.pay_cycle_months, data.advance_days, data.occupants, data.signed_date or today, status, data.note, user_id),
            ).fetchone()["id"]
            for fee in fees:
                conn.execute("INSERT INTO lease_fees (lease_id, fee_item_id, name, kind, price) VALUES (%s, %s, %s, %s, %s)",
                             (lease_id, fee["fee_item_id"], fee["name"], fee["kind"], fee["price"]))
            for bill in bills:
                insert_bill(conn, landlord_id=landlord_id, lease_id=lease_id, bill=bill)
            # 已出租时段写入不可租表，前台按日期找房自动避开；半开区间所以到期日 +1
            block_id = conn.execute(
                "INSERT INTO listing_unavailability (listing_id, start_date, end_date, kind, note) "
                "VALUES (%s, %s, %s, 'lease', '') RETURNING id",
                (data.listing_id, data.start_date, data.end_date + timedelta(days=1)),
            ).fetchone()["id"]
            conn.execute(
                "UPDATE leases SET unavailability_id = %s, "
                "lease_no = 'HT' || to_char(now(), 'YYYYMMDD') || lpad(id::text, 6, '0') WHERE id = %s",
                (block_id, lease_id),
            )
            if listing["status"] == "published":
                conn.execute("UPDATE listings SET status = 'offline', updated_at = now() WHERE id = %s", (data.listing_id,))
            if data.inquiry_id is not None:
                conn.execute("UPDATE listing_inquiries SET status = 'closed', handled_at = coalesce(handled_at, now()) "
                             "WHERE id = %s AND landlord_id = %s", (data.inquiry_id, landlord_id))
            return lease_id

    @staticmethod
    def _check_overlap(conn, data: SignInput) -> None:
        if (data.end_date - data.start_date).days > 3653:
            raise Conflict("单份租约最长 10 年")
        if conn.execute("SELECT 1 FROM leases WHERE listing_id = %s AND status = 'expired' LIMIT 1",
                        (data.listing_id,)).fetchone():
            raise Conflict("该房源有已到期未退租的租约，请先办理退租")
        clash = conn.execute(
            "SELECT lease_no, start_date, end_date FROM leases WHERE listing_id = %s AND status IN ('pending', 'active') "
            "AND start_date <= %s AND end_date >= %s LIMIT 1",
            (data.listing_id, data.end_date, data.start_date),
        ).fetchone()
        if clash:
            raise Conflict(f"与租约 {clash['lease_no']}（{clash['start_date']} 至 {clash['end_date']}）日期重叠")

    def _renter(self, conn, landlord_id: int, data: SignInput) -> int:
        if data.renter_id is not None:
            if conn.execute("SELECT 1 FROM renters WHERE id = %s AND landlord_id = %s", (data.renter_id, landlord_id)).fetchone() is None:
                raise NotFound("租客不存在")
            return data.renter_id
        if not data.new_renter:
            raise Conflict("请选择或新建租客")
        cols = ", ".join(data.new_renter)
        return conn.execute(
            f"INSERT INTO renters (landlord_id, {cols}) VALUES (%s, {', '.join(['%s'] * len(data.new_renter))}) RETURNING id",
            (landlord_id, *data.new_renter.values()),
        ).fetchone()["id"]

    # ---- 查询 ----------------------------------------------------------

    def list(self, landlord_id: int, *, status: str | None, keyword: str | None, expiring: bool,
             today: date, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        clauses, params = ["l.landlord_id = %s"], [landlord_id]
        if status:
            clauses.append("l.status = %s")
            params.append(status)
        if keyword:
            clauses.append("(r.name ILIKE %s OR r.phone ILIKE %s OR s.title ILIKE %s OR l.lease_no ILIKE %s)")
            params += [like_pattern(keyword)] * 4
        if expiring:
            clauses.append("l.status = 'active' AND l.end_date BETWEEN %s AND %s")
            params += [today, today + timedelta(days=EXPIRING_DAYS)]
        where = " AND ".join(clauses)
        base = "FROM leases l JOIN renters r ON r.id = l.renter_id JOIN listings s ON s.id = l.listing_id"
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n {base} WHERE {where}", params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {LIST_COLUMNS} {base} {OUTSTANDING_JOIN} WHERE {where} "
                "ORDER BY (l.status IN ('active', 'expired', 'pending')) DESC, l.start_date DESC, l.id DESC LIMIT %s OFFSET %s",
                (today, *params, limit, offset),
            ).fetchall()
        return rows, total

    def get(self, landlord_id: int, lease_id: int, *, today: date) -> dict[str, Any]:
        with self._db.transaction() as conn:
            lease = conn.execute(
                f"SELECT {LIST_COLUMNS}, l.advance_days, l.occupants, l.signed_date, l.note, l.checkout_note, "
                "l.deposit_offset, l.deposit_refund, r.id_card_tail "
                "FROM leases l JOIN renters r ON r.id = l.renter_id JOIN listings s ON s.id = l.listing_id "
                f"{OUTSTANDING_JOIN} WHERE l.landlord_id = %s AND l.id = %s",
                (today, landlord_id, lease_id),
            ).fetchone()
            if lease is None:
                raise NotFound("租约不存在")
            fees = conn.execute("SELECT fee_item_id, name, kind, price FROM lease_fees WHERE lease_id = %s ORDER BY id",
                                (lease_id,)).fetchall()
            bills = conn.execute(
                "SELECT id, bill_no, kind, period_no, period_start, period_end, due_date, total_amount, discount_amount, "
                "paid_amount, status, settled_at, note FROM bills WHERE lease_id = %s "
                "ORDER BY (kind = 'deposit') DESC, due_date, period_no NULLS LAST, id",
                (lease_id,),
            ).fetchall()
            readings = conn.execute(
                "SELECT m.id, m.fee_item_id, f.name AS fee_name, f.unit, m.prev_reading, m.reading, m.read_date, m.usage, "
                "m.unit_price, m.amount, m.bill_id, b.bill_no FROM meter_readings m JOIN fee_items f ON f.id = m.fee_item_id "
                "LEFT JOIN bills b ON b.id = m.bill_id WHERE m.lease_id = %s ORDER BY m.read_date DESC, m.id DESC",
                (lease_id,),
            ).fetchall()
        return {**lease, "fees": fees, "bills": bills, "readings": readings}

    # ---- 修改与作废 ----------------------------------------------------

    def update_meta(self, landlord_id: int, lease_id: int, *, occupants: int, signed_date: date | None, note: str) -> None:
        """只能改入住人数、签约日期、备注；日期、金额、房源、租客需作废重签。"""
        with self._db.transaction() as conn:
            row = conn.execute(
                "UPDATE leases SET occupants = %s, signed_date = %s, note = %s, updated_at = now() "
                "WHERE id = %s AND landlord_id = %s AND status <> 'void' RETURNING id",
                (occupants, signed_date, note, lease_id, landlord_id),
            ).fetchone()
        if row is None:
            raise NotFound("租约不存在")

    def void(self, landlord_id: int, lease_id: int) -> None:
        """仅限没有任何有效收款的租约：作废全部账单并释放已出租时段。"""
        with self._db.transaction() as conn:
            lease = conn.execute("SELECT status, unavailability_id FROM leases WHERE id = %s AND landlord_id = %s FOR UPDATE",
                                 (lease_id, landlord_id)).fetchone()
            if lease is None:
                raise NotFound("租约不存在")
            if lease["status"] not in OPEN_STATUSES:
                raise Conflict("租约已退租或已作废")
            paid = conn.execute(
                "SELECT 1 FROM payments p JOIN bills b ON b.id = p.bill_id WHERE b.lease_id = %s AND p.status = 'valid' LIMIT 1",
                (lease_id,),
            ).fetchone()
            if paid:
                raise Conflict("租约已有收款记录，不能作废，请办理退租")
            conn.execute("UPDATE bills SET status = 'void', updated_at = now() WHERE lease_id = %s", (lease_id,))
            conn.execute("UPDATE leases SET status = 'void', unavailability_id = NULL, updated_at = now() WHERE id = %s", (lease_id,))
            if lease["unavailability_id"]:
                conn.execute("DELETE FROM listing_unavailability WHERE id = %s", (lease["unavailability_id"],))

    # ---- 每日任务 ------------------------------------------------------

    def advance_statuses(self, today: date) -> dict[str, int]:
        """待生效到起租日 → 生效中；生效中过了到期日 → 已到期（等房东退租）。可重复执行。"""
        with self._db.transaction() as conn:
            activated = conn.execute("UPDATE leases SET status = 'active', updated_at = now() "
                                     "WHERE status = 'pending' AND start_date <= %s", (today,)).rowcount
            expired = conn.execute("UPDATE leases SET status = 'expired', updated_at = now() "
                                   "WHERE status = 'active' AND end_date < %s", (today,)).rowcount
        return {"activated": activated, "expired": expired}
