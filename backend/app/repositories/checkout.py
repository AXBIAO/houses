"""退租结算（只记账）。顺序与 ruoyi 版一致：
1. 作废「账期开始日晚于退租日且未收款」的租金账单——挂在上面的抄表先解绑，避免水电费随账单一起作废而丢失；
2. 未出账的水电 + 追加费用生成一张退租结算账单；
3. 已收押金按应收日从早到晚抵扣欠费（登记为「押金抵扣」）；
4. 剩余押金登记为「退押金」负数流水（实际退款由房东线下完成），押金账单关闭；没收到的押金账单直接作废；
5. 租约改为已退租，已出租时段截止到退租日。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.billing import ZERO, BillLedger, PlannedBill, PlannedItem, money
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.ledger_ops import apply, insert_bill, insert_payment, ledger_of, save_ledger


@dataclass(frozen=True)
class ExtraCharge:
    name: str
    amount: Decimal


class CheckoutRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def checkout(self, landlord_id: int, lease_id: int, *, checkout_date: date, extras: tuple[ExtraCharge, ...],
                 note: str, user_id: int) -> dict[str, Any]:
        with self._db.transaction() as conn:
            lease = conn.execute("SELECT * FROM leases WHERE id = %s AND landlord_id = %s FOR UPDATE",
                                 (lease_id, landlord_id)).fetchone()
            if lease is None:
                raise NotFound("租约不存在")
            if lease["status"] not in ("active", "expired"):
                raise Conflict("只有生效中或已到期的租约可以退租")
            if checkout_date < lease["start_date"]:
                raise Conflict("退租日期不能早于起租日，未开始的租约请作废")
            # 后续所有账单都在本事务内改动，先整体加锁
            conn.execute("SELECT id FROM bills WHERE lease_id = %s FOR UPDATE", (lease_id,))

            voided = self._void_future_rent(conn, lease_id, checkout_date)
            settlement_id = self._settlement_bill(conn, landlord_id, lease_id, checkout_date, extras)
            offset, refund = self._apply_deposit(conn, landlord_id, lease_id, checkout_date, user_id)

            conn.execute(
                "UPDATE leases SET status = 'checked_out', checkout_date = %s, checkout_note = %s, deposit_offset = %s, "
                "deposit_refund = %s, updated_at = now() WHERE id = %s",
                (checkout_date, note, offset, refund, lease_id),
            )
            if lease["unavailability_id"]:
                conn.execute("UPDATE listing_unavailability SET end_date = %s WHERE id = %s",
                             (checkout_date + timedelta(days=1), lease["unavailability_id"]))
            remaining = conn.execute(
                "SELECT coalesce(sum(total_amount - discount_amount - paid_amount), 0) AS n FROM bills "
                "WHERE lease_id = %s AND status IN ('unpaid', 'partial')",
                (lease_id,),
            ).fetchone()["n"]
        return {"voidedBills": voided, "settlementBillId": settlement_id, "depositOffset": offset,
                "depositRefund": refund, "outstanding": money(remaining)}

    @staticmethod
    def _void_future_rent(conn, lease_id: int, checkout_date: date) -> int:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM bills WHERE lease_id = %s AND kind = 'rent' AND status <> 'void' AND period_start > %s "
            "AND paid_amount = 0", (lease_id, checkout_date),
        ).fetchall()]
        if ids:
            conn.execute("UPDATE meter_readings SET bill_id = NULL WHERE bill_id = ANY(%s)", (ids,))
            conn.execute("UPDATE bills SET status = 'void', updated_at = now() WHERE id = ANY(%s)", (ids,))
        return len(ids)

    @staticmethod
    def _settlement_bill(conn, landlord_id: int, lease_id: int, checkout_date: date,
                         extras: tuple[ExtraCharge, ...]) -> int | None:
        readings = conn.execute(
            "SELECT m.id, m.fee_item_id, f.name, m.usage, m.unit_price, m.amount FROM meter_readings m "
            "JOIN fee_items f ON f.id = m.fee_item_id WHERE m.lease_id = %s AND m.bill_id IS NULL AND m.amount > 0 "
            "ORDER BY m.read_date, m.id",
            (lease_id,),
        ).fetchall()
        items = [PlannedItem(r["fee_item_id"], r["name"], money(r["usage"]), Decimal(r["unit_price"]), money(r["amount"]))
                 for r in readings]
        meter_ids: list[int | None] = [r["id"] for r in readings]
        for extra in extras:
            items.append(PlannedItem(None, extra.name, Decimal("1.00"), money(extra.amount), money(extra.amount)))
            meter_ids.append(None)
        if not items:
            return None
        bill = PlannedBill("settlement", None, checkout_date, checkout_date, checkout_date, tuple(items))
        bill_id = insert_bill(conn, landlord_id=landlord_id, lease_id=lease_id, bill=bill, meter_ids=meter_ids, note="退租结算")
        if readings:
            conn.execute("UPDATE meter_readings SET bill_id = %s WHERE id = ANY(%s)", (bill_id, [r["id"] for r in readings]))
        return bill_id

    @staticmethod
    def _apply_deposit(conn, landlord_id: int, lease_id: int, checkout_date: date, user_id: int) -> tuple[Decimal, Decimal]:
        deposit = conn.execute("SELECT * FROM bills WHERE lease_id = %s AND kind = 'deposit' AND status <> 'void' LIMIT 1",
                               (lease_id,)).fetchone()
        if deposit is None:
            return ZERO, ZERO
        held = money(deposit["paid_amount"])
        if held == 0:
            conn.execute("UPDATE bills SET status = 'void', note = '退租时押金未收，作废', updated_at = now() WHERE id = %s",
                         (deposit["id"],))
            return ZERO, ZERO

        remaining, offset_total = held, ZERO
        debts = conn.execute(
            "SELECT * FROM bills WHERE lease_id = %s AND kind <> 'deposit' AND status IN ('unpaid', 'partial') "
            "ORDER BY due_date, id", (lease_id,),
        ).fetchall()
        for debt in debts:
            if remaining == 0:
                break
            ledger = ledger_of(debt)
            used = min(ledger.outstanding, remaining)
            save_ledger(conn, debt["id"], apply(ledger, "pay", used))
            insert_payment(conn, landlord_id=landlord_id, bill_id=debt["id"], amount=used, method="deposit_offset",
                           paid_on=checkout_date, note="退租押金抵扣", user_id=user_id)
            remaining -= used
            offset_total += used

        if remaining > 0:
            insert_payment(conn, landlord_id=landlord_id, bill_id=deposit["id"], amount=-remaining, method="deposit_refund",
                           paid_on=checkout_date, note="退还押金（线下退款）", user_id=user_id)
        # 押金账单关闭：已收 = 用于抵扣的部分，其余（含当初未收齐的差额）记为减免，使 应收 = 减免 + 已收
        kept = held - remaining
        total = money(deposit["total_amount"])
        save_ledger(conn, deposit["id"], BillLedger(total, total - kept, kept), status="settled")
        return money(offset_total), money(remaining)
