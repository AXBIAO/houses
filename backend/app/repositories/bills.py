"""账单与收款流水。平台只记账：收款是房东登记线下收到的钱，作废只是撤销这条登记。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.ledger_ops import MANUAL_METHODS, apply, insert_payment, ledger_of, lock_bill, save_ledger
from backend.app.repositories.sql_helpers import like_pattern

BILL_COLUMNS = """
    b.id, b.bill_no, b.lease_id, l.lease_no, b.kind, b.period_no, b.period_start, b.period_end, b.due_date,
    b.total_amount, b.discount_amount, b.paid_amount, b.status, b.settled_at, b.note,
    greatest(b.total_amount - b.discount_amount - b.paid_amount, 0) AS outstanding,
    r.name AS renter_name, r.phone AS renter_phone, s.title AS listing_title
"""
BILL_FROM = "FROM bills b JOIN leases l ON l.id = b.lease_id JOIN renters r ON r.id = l.renter_id JOIN listings s ON s.id = l.listing_id"


class BillRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def list(self, landlord_id: int, *, status: str | None, overdue: bool, lease_id: int | None, keyword: str | None,
             due_from: date | None, due_to: date | None, today: date, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        clauses, params = ["b.landlord_id = %s"], [landlord_id]
        if status == "open":
            clauses.append("b.status IN ('unpaid', 'partial')")
        elif status:
            clauses.append("b.status = %s")
            params.append(status)
        if overdue:
            clauses.append("b.status IN ('unpaid', 'partial') AND b.due_date < %s")
            params.append(today)
        if lease_id is not None:
            clauses.append("b.lease_id = %s")
            params.append(lease_id)
        if keyword:
            clauses.append("(r.name ILIKE %s OR r.phone ILIKE %s OR s.title ILIKE %s OR b.bill_no ILIKE %s)")
            params += [like_pattern(keyword)] * 4
        if due_from:
            clauses.append("b.due_date >= %s")
            params.append(due_from)
        if due_to:
            clauses.append("b.due_date <= %s")
            params.append(due_to)
        where = " AND ".join(clauses)
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n {BILL_FROM} WHERE {where}", params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {BILL_COLUMNS}, (b.status IN ('unpaid', 'partial') AND b.due_date < %s) AS is_overdue "
                f"{BILL_FROM} WHERE {where} ORDER BY (b.status IN ('unpaid', 'partial')) DESC, b.due_date, b.id "
                "LIMIT %s OFFSET %s",
                (today, *params, limit, offset),
            ).fetchall()
        return rows, total

    def summary(self, landlord_id: int, *, today: date, month_start: date, month_end: date) -> dict[str, Any]:
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT "
                "coalesce(sum(total_amount - discount_amount - paid_amount) FILTER (WHERE status IN ('unpaid','partial') AND due_date < %s), 0) AS overdue_amount, "
                "count(*) FILTER (WHERE status IN ('unpaid','partial') AND due_date < %s) AS overdue_count, "
                "coalesce(sum(total_amount - discount_amount) FILTER (WHERE status <> 'void' AND due_date BETWEEN %s AND %s), 0) AS month_receivable, "
                "coalesce(sum(total_amount - discount_amount - paid_amount) FILTER (WHERE status IN ('unpaid','partial') AND due_date BETWEEN %s AND %s), 0) AS month_outstanding "
                "FROM bills WHERE landlord_id = %s",
                (today, today, month_start, month_end, month_start, month_end, landlord_id),
            ).fetchone() | {"month_collected": self._collected(landlord_id, month_start, month_end)}

    def _collected(self, landlord_id: int, start: date, end: date) -> Decimal:
        """本月登记的实收（不含押金抵扣这类内部转账，含退押金负数）。"""
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT coalesce(sum(amount), 0) AS n FROM payments WHERE landlord_id = %s AND status = 'valid' "
                "AND method <> 'deposit_offset' AND paid_on BETWEEN %s AND %s",
                (landlord_id, start, end),
            ).fetchone()["n"]

    def get(self, landlord_id: int, bill_id: int, *, today: date) -> dict[str, Any]:
        with self._db.transaction() as conn:
            bill = conn.execute(
                f"SELECT {BILL_COLUMNS}, (b.status IN ('unpaid', 'partial') AND b.due_date < %s) AS is_overdue "
                f"{BILL_FROM} WHERE b.landlord_id = %s AND b.id = %s",
                (today, landlord_id, bill_id),
            ).fetchone()
            if bill is None:
                raise NotFound("账单不存在")
            items = conn.execute("SELECT id, name, quantity, unit_price, amount, meter_reading_id FROM bill_items "
                                 "WHERE bill_id = %s ORDER BY id", (bill_id,)).fetchall()
            payments = conn.execute("SELECT id, amount, method, paid_on, note, status, voided_at, created_at FROM payments "
                                    "WHERE bill_id = %s ORDER BY created_at, id", (bill_id,)).fetchall()
        return {**bill, "items": items, "payments": payments}

    # ---- 写操作 --------------------------------------------------------

    def pay(self, landlord_id: int, bill_id: int, *, amount: Decimal, method: str, paid_on: date, note: str,
            user_id: int) -> dict[str, Any]:
        if method not in MANUAL_METHODS:
            raise Conflict("押金抵扣和退押金由退租结算自动登记")
        with self._db.transaction() as conn:
            bill = lock_bill(conn, landlord_id, bill_id)
            if bill["status"] == "void":
                raise Conflict("账单已作废")
            ledger = apply(ledger_of(bill), "pay", amount)
            save_ledger(conn, bill_id, ledger)
            return insert_payment(conn, landlord_id=landlord_id, bill_id=bill_id, amount=amount, method=method,
                                  paid_on=paid_on, note=note, user_id=user_id)

    def discount(self, landlord_id: int, bill_id: int, amount: Decimal, note: str | None) -> None:
        with self._db.transaction() as conn:
            bill = lock_bill(conn, landlord_id, bill_id)
            if bill["status"] == "void":
                raise Conflict("账单已作废")
            if bill["lease_status"] == "checked_out" and bill["kind"] == "deposit":
                raise Conflict("已退租结算的押金账单不能修改")
            save_ledger(conn, bill_id, apply(ledger_of(bill), "discount", amount))
            if note is not None:
                conn.execute("UPDATE bills SET note = %s WHERE id = %s", (note, bill_id))

    def void_payment(self, landlord_id: int, payment_id: int) -> None:
        with self._db.transaction() as conn:
            payment = conn.execute("SELECT id, bill_id, amount, method, status FROM payments "
                                   "WHERE id = %s AND landlord_id = %s FOR UPDATE", (payment_id, landlord_id)).fetchone()
            if payment is None:
                raise NotFound("收款记录不存在")
            if payment["status"] != "valid":
                raise Conflict("收款记录已作废")
            if payment["method"] not in MANUAL_METHODS:
                raise Conflict("押金抵扣与退押金记录随退租结算生成，不能单独作废")
            bill = lock_bill(conn, landlord_id, payment["bill_id"])
            if bill["lease_status"] == "checked_out":
                raise Conflict("租约已退租结算，不能作废收款")
            save_ledger(conn, bill["id"], apply(ledger_of(bill), "reverse", payment["amount"]))
            conn.execute("UPDATE payments SET status = 'void', voided_at = now() WHERE id = %s", (payment_id,))

    def payments(self, landlord_id: int, *, method: str | None, date_from: date | None, date_to: date | None,
                 limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        clauses, params = ["p.landlord_id = %s"], [landlord_id]
        if method:
            clauses.append("p.method = %s")
            params.append(method)
        if date_from:
            clauses.append("p.paid_on >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("p.paid_on <= %s")
            params.append(date_to)
        where = " AND ".join(clauses)
        base = ("FROM payments p JOIN bills b ON b.id = p.bill_id JOIN leases l ON l.id = b.lease_id "
                "JOIN renters r ON r.id = l.renter_id JOIN listings s ON s.id = l.listing_id")
        with self._db.transaction() as conn:
            total = conn.execute(f"SELECT count(*) AS n {base} WHERE {where}", params).fetchone()["n"]
            rows = conn.execute(
                "SELECT p.id, p.amount, p.method, p.paid_on, p.note, p.status, p.voided_at, p.created_at, p.bill_id, "
                f"b.bill_no, b.kind AS bill_kind, l.id AS lease_id, r.name AS renter_name, s.title AS listing_title {base} "
                f"WHERE {where} ORDER BY p.paid_on DESC, p.id DESC LIMIT %s OFFSET %s",
                (*params, limit, offset),
            ).fetchall()
        return rows, total
