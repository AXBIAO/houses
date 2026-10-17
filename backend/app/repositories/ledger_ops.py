"""账单写操作的共用部分：在调用方的事务里执行，账单行先 FOR UPDATE 锁住再改，避免并发收款算错。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.domain.billing import BillLedger, PlannedBill, PlannedItem, money
from backend.app.domain.errors import Conflict, NotFound

MANUAL_METHODS = frozenset({"cash", "wechat", "alipay", "bank", "other"})


def lock_bill(conn, landlord_id: int, bill_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT b.*, l.status AS lease_status FROM bills b JOIN leases l ON l.id = b.lease_id "
        "WHERE b.id = %s AND b.landlord_id = %s FOR UPDATE OF b",
        (bill_id, landlord_id),
    ).fetchone()
    if row is None:
        raise NotFound("账单不存在")
    return row


def ledger_of(bill: dict[str, Any]) -> BillLedger:
    return BillLedger(bill["total_amount"], bill["discount_amount"], bill["paid_amount"])


def save_ledger(conn, bill_id: int, ledger: BillLedger, *, status: str | None = None) -> None:
    """写回金额与状态；状态默认由账本推导，结清时记录结清时间。"""
    final = status or ledger.status
    conn.execute(
        "UPDATE bills SET total_amount = %s, discount_amount = %s, paid_amount = %s, status = %s, "
        "settled_at = CASE WHEN %s = 'settled' THEN coalesce(settled_at, now()) ELSE NULL END, updated_at = now() "
        "WHERE id = %s",
        (ledger.total_amount, ledger.discount_amount, ledger.paid, final, final, bill_id),
    )


def apply(ledger: BillLedger, op: str, amount: Decimal | None) -> BillLedger:
    """把账本校验错误（ValueError）统一转成业务冲突。"""
    try:
        return getattr(ledger, op)(amount)
    except ValueError as exc:
        raise Conflict(str(exc)) from exc


def insert_payment(conn, *, landlord_id: int, bill_id: int, amount: Decimal, method: str, paid_on: date,
                   note: str, user_id: int | None) -> dict[str, Any]:
    return conn.execute(
        "INSERT INTO payments (landlord_id, bill_id, amount, method, paid_on, note, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, bill_id, amount, method, paid_on, note, status, created_at",
        (landlord_id, bill_id, money(amount), method, paid_on, note, user_id),
    ).fetchone()


def insert_items(conn, bill_id: int, items: list[PlannedItem], meter_ids: list[int | None] | None = None) -> None:
    for index, item in enumerate(items):
        conn.execute(
            "INSERT INTO bill_items (bill_id, fee_item_id, meter_reading_id, name, quantity, unit_price, amount) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (bill_id, item.item_id, meter_ids[index] if meter_ids else None, item.item_name, item.quantity,
             item.unit_price, item.amount),
        )


def insert_bill(conn, *, landlord_id: int, lease_id: int, bill: PlannedBill, note: str = "",
                meter_ids: list[int | None] | None = None) -> int:
    row = conn.execute(
        "INSERT INTO bills (landlord_id, lease_id, kind, period_no, period_start, period_end, due_date, total_amount, note) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (landlord_id, lease_id, bill.kind, bill.period_no, bill.period_start, bill.period_end, bill.due_date,
         bill.total_amount, note),
    ).fetchone()
    conn.execute("UPDATE bills SET bill_no = 'ZD' || to_char(now(), 'YYYYMMDD') || lpad(id::text, 6, '0') WHERE id = %s",
                 (row["id"],))
    insert_items(conn, row["id"], list(bill.items), meter_ids)
    if bill.total_amount == 0:
        save_ledger(conn, row["id"], BillLedger(bill.total_amount))
    return row["id"]
