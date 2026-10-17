"""抄表：读数属于房间，费用即时记入租约账单（抄表日之后最近一期未结清的租金账单，没有就单出一张）。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle
from backend.app.domain.billing import BillLedger, PlannedBill, PlannedItem, money
from backend.app.domain.errors import Conflict, NotFound
from backend.app.repositories.ledger_ops import insert_bill, ledger_of, lock_bill, save_ledger


class MeterRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def last_reading(self, landlord_id: int, lease_id: int, fee_item_id: int) -> dict[str, Any] | None:
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT m.reading, m.read_date FROM meter_readings m JOIN leases l ON l.listing_id = m.listing_id "
                "WHERE l.id = %s AND l.landlord_id = %s AND m.fee_item_id = %s ORDER BY m.read_date DESC, m.id DESC LIMIT 1",
                (lease_id, landlord_id, fee_item_id),
            ).fetchone()

    def create(self, landlord_id: int, lease_id: int, *, fee_item_id: int, reading: Decimal, read_date: date,
               prev_reading: Decimal | None) -> dict[str, Any]:
        with self._db.transaction() as conn:
            lease = conn.execute("SELECT id, listing_id, status FROM leases WHERE id = %s AND landlord_id = %s FOR UPDATE",
                                 (lease_id, landlord_id)).fetchone()
            if lease is None:
                raise NotFound("租约不存在")
            if lease["status"] not in ("active", "expired"):
                raise Conflict("只有生效中或已到期的租约可以抄表")
            item = conn.execute("SELECT id, name, kind, default_price, unit FROM fee_items WHERE id = %s AND landlord_id = %s",
                                (fee_item_id, landlord_id)).fetchone()
            if item is None:
                raise NotFound("收费项目不存在")
            if item["kind"] != "metered":
                raise Conflict("只有按表计量的项目可以抄表")
            last = conn.execute(
                "SELECT reading, read_date FROM meter_readings WHERE listing_id = %s AND fee_item_id = %s "
                "ORDER BY read_date DESC, id DESC LIMIT 1 FOR UPDATE",
                (lease["listing_id"], fee_item_id),
            ).fetchone()
            if last and read_date < last["read_date"]:
                raise Conflict(f"抄表日期不能早于上次（{last['read_date']}）")
            # 上次读数自动带出；首次抄表或换表时由房东填写起始读数
            prev = prev_reading if prev_reading is not None else (last["reading"] if last else None)
            if prev is None:
                raise Conflict("首次抄表请填写起始读数")
            if reading < prev:
                raise Conflict(f"读数不能小于起始读数 {prev}")
            lease_fee = conn.execute("SELECT price FROM lease_fees WHERE lease_id = %s AND fee_item_id = %s",
                                     (lease_id, fee_item_id)).fetchone()
            unit_price = Decimal(lease_fee["price"] if lease_fee else item["default_price"])
            usage = money(Decimal(reading) - Decimal(prev))
            amount = money(usage * unit_price)
            row = conn.execute(
                "INSERT INTO meter_readings (landlord_id, lease_id, listing_id, fee_item_id, prev_reading, reading, read_date, "
                "usage, unit_price, amount) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (landlord_id, lease_id, lease["listing_id"], fee_item_id, prev, reading, read_date, usage, unit_price, amount),
            ).fetchone()
            bill_id = None
            if amount > 0:
                bill_id = self._bill(conn, landlord_id, lease_id, row["id"],
                                     PlannedItem(fee_item_id, item["name"], usage, unit_price, amount), read_date)
            return {"id": row["id"], "usage": usage, "unitPrice": unit_price, "amount": amount, "billId": bill_id}

    @staticmethod
    def _bill(conn, landlord_id: int, lease_id: int, reading_id: int, item: PlannedItem, read_date: date) -> int:
        target = conn.execute(
            "SELECT id FROM bills WHERE lease_id = %s AND kind = 'rent' AND status IN ('unpaid', 'partial') "
            "AND period_start >= %s ORDER BY period_start LIMIT 1 FOR UPDATE",
            (lease_id, read_date),
        ).fetchone()
        if target is None:
            bill = PlannedBill("other", None, read_date, read_date, read_date, (item,))
            bill_id = insert_bill(conn, landlord_id=landlord_id, lease_id=lease_id, bill=bill, meter_ids=[reading_id])
        else:
            bill_id = target["id"]
            conn.execute(
                "INSERT INTO bill_items (bill_id, fee_item_id, meter_reading_id, name, quantity, unit_price, amount) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (bill_id, item.item_id, reading_id, item.item_name, item.quantity, item.unit_price, item.amount),
            )
            current = lock_bill(conn, landlord_id, bill_id)
            ledger = ledger_of(current)
            save_ledger(conn, bill_id, BillLedger(ledger.total_amount + item.amount, ledger.discount_amount, ledger.paid))
        conn.execute("UPDATE meter_readings SET bill_id = %s WHERE id = %s", (bill_id, reading_id))
        return bill_id

    def delete(self, landlord_id: int, reading_id: int) -> None:
        """只能删除该房间该项目的最新一条；已记入账单的，账单不能已有收款。"""
        with self._db.transaction() as conn:
            row = conn.execute("SELECT * FROM meter_readings WHERE id = %s AND landlord_id = %s FOR UPDATE",
                               (reading_id, landlord_id)).fetchone()
            if row is None:
                raise NotFound("抄表记录不存在")
            latest = conn.execute(
                "SELECT id FROM meter_readings WHERE listing_id = %s AND fee_item_id = %s ORDER BY read_date DESC, id DESC LIMIT 1",
                (row["listing_id"], row["fee_item_id"]),
            ).fetchone()
            if latest["id"] != reading_id:
                raise Conflict("只能删除最新一条抄表记录")
            if row["bill_id"] is not None:
                bill = lock_bill(conn, landlord_id, row["bill_id"])
                if bill["status"] != "void":
                    if Decimal(bill["paid_amount"]) != 0:
                        raise Conflict("所在账单已有收款，不能删除，可在账单上减免")
                    ledger = ledger_of(bill)
                    new_total = ledger.total_amount - Decimal(row["amount"])
                    if ledger.discount_amount > new_total:
                        raise Conflict("所在账单的减免金额超过删除后的应收，请先调整减免")
                    conn.execute("DELETE FROM bill_items WHERE bill_id = %s AND meter_reading_id = %s", (bill["id"], reading_id))
                    if new_total == 0 and bill["kind"] == "other":
                        save_ledger(conn, bill["id"], BillLedger(new_total, ledger.discount_amount, ledger.paid), status="void")
                    else:
                        save_ledger(conn, bill["id"], BillLedger(new_total, ledger.discount_amount, ledger.paid))
            conn.execute("UPDATE bill_items SET meter_reading_id = NULL WHERE meter_reading_id = %s", (reading_id,))
            conn.execute("DELETE FROM meter_readings WHERE id = %s", (reading_id,))

