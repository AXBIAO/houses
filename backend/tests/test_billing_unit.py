"""移植自 ruoyi 版 BillPlannerTest（12 个）与 BillLedgerTest（12 个），断言逐条对应。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.domain.billing import BillLedger, FixedFee, LeaseTerms, plan_bills

RENT = Decimal("3000.00")


def d(text: str) -> date:
    return date.fromisoformat(text)


def m(text: str) -> Decimal:
    return Decimal(text)


def terms(start: str, end: str, cycle: int, **kw) -> LeaseTerms:
    base = {"monthly_rent": RENT, "deposit": Decimal("0"), "advance_days": 0, "fees": ()}
    base.update(kw)
    return LeaseTerms(d(start), d(end), pay_cycle_months=cycle, **base)


def rent_bills(bills):
    return [b for b in bills if b.kind == "rent"]


# ---- BillPlanner ----------------------------------------------------------

def test_monthly_full_year():
    """月付一年：12 期，每期一个自然月，金额等于月租"""
    bills = plan_bills(terms("2026-11-01", "2027-10-31", 1))
    assert len(bills) == 12
    first = bills[0]
    assert (first.period_no, first.period_start, first.period_end, first.due_date) == (
        1, d("2026-11-01"), d("2026-11-30"), d("2026-11-01"))
    assert all(b.total_amount == RENT for b in bills)
    assert bills[11].period_end == d("2027-10-31")


def test_quarterly_full_year():
    """季付一年：4 期，每期 3 个月租金"""
    bills = plan_bills(terms("2026-11-01", "2027-10-31", 3))
    assert len(bills) == 4
    assert bills[0].period_end == d("2027-01-31")
    assert bills[1].period_start == d("2027-02-01")
    assert all(b.total_amount == m("9000.00") for b in bills)


def test_yearly():
    """年付一年：1 期，12 个月租金"""
    bills = plan_bills(terms("2026-11-01", "2027-10-31", 12))
    assert len(bills) == 1 and bills[0].total_amount == m("36000.00")


def test_last_period_partial():
    """最后一期不满一个周期：整月按月租，零头天数按 月租/30 计"""
    bills = plan_bills(terms("2026-11-01", "2027-05-15", 3))
    assert len(bills) == 3
    last = bills[2]
    assert (last.period_start, last.period_end) == (d("2027-05-01"), d("2027-05-15"))
    assert last.total_amount == m("1500.00")
    assert last.items[0].quantity == m("0.50")


def test_last_period_months_and_days():
    """最后一期含整月和零头：1 个整月 + 10 天"""
    last = plan_bills(terms("2026-11-01", "2027-03-10", 3))[1]
    assert last.period_start == d("2027-02-01")
    assert last.total_amount == m("4000.00")


def test_start_on_month_end():
    """1 月 31 日起租：月末日期每期都从起租日推算，不会越推越早"""
    bills = plan_bills(terms("2027-01-31", "2027-04-29", 1))
    assert len(bills) == 3
    assert bills[0].period_end == d("2027-02-27")
    assert (bills[1].period_start, bills[1].period_end) == (d("2027-02-28"), d("2027-03-30"))
    assert bills[2].period_start == d("2027-03-31")
    assert all(b.total_amount == RENT for b in bills)


def test_advance_days():
    """提前收租天数：应收日 = 账期开始日 - 提前天数"""
    bills = plan_bills(terms("2026-11-01", "2027-10-31", 1, advance_days=5))
    assert bills[0].due_date == d("2026-10-27")
    assert bills[1].due_date == d("2026-11-26")


def test_deposit_bill():
    """押金大于 0 时单独出一张押金账单，应收日为起租日"""
    bills = plan_bills(terms("2026-11-01", "2027-10-31", 1, deposit=m("3000"), advance_days=5))
    assert len(bills) == 13
    deposit = bills[0]
    assert deposit.kind == "deposit" and deposit.period_no is None
    assert deposit.due_date == d("2026-11-01")
    assert deposit.total_amount == m("3000")
    assert deposit.items[0].item_name == "押金"


def test_no_deposit_bill():
    """押金为 0 或空时不出押金账单"""
    assert all(b.kind != "deposit" for b in plan_bills(terms("2026-11-01", "2027-10-31", 1, deposit=None)))


def test_fixed_and_one_time_fees():
    """固定费用按每期月数计入，一次性费用只计入第一期"""
    fees = (FixedFee(11, "管理费", m("50"), False), FixedFee(12, "门卡工本费", m("20"), True))
    bills = rent_bills(plan_bills(terms("2026-11-01", "2027-10-31", 3, fees=fees)))
    first, second = bills[0], bills[1]
    assert len(first.items) == 3 and first.total_amount == m("9170.00")
    assert len(second.items) == 2 and second.total_amount == m("9150.00")
    fee = second.items[1]
    assert fee.item_id == 11 and fee.quantity == m("3")


def test_total_rent_matches():
    """一年的租金合计正好等于 12 个月租"""
    total = sum(b.total_amount for b in plan_bills(terms("2026-11-15", "2027-11-14", 1)))
    assert total == m("36000.00")


def test_invalid_terms():
    """到期日早于起租日、付款周期小于 1、月租为负 都拒绝"""
    with pytest.raises(ValueError):
        plan_bills(terms("2026-11-01", "2026-10-31", 1))
    with pytest.raises(ValueError):
        plan_bills(terms("2026-11-01", "2027-10-31", 0))
    with pytest.raises(ValueError):
        plan_bills(terms("2026-11-01", "2027-10-31", 1, monthly_rent=m("-1")))


# ---- BillLedger -----------------------------------------------------------

def bill(total: str, discount: str, paid: str) -> BillLedger:
    return BillLedger(m(total), m(discount), m(paid))


def test_unpaid():
    """没收款：待收 = 应收，状态待收"""
    b = bill("2850", "0", "0")
    assert b.outstanding == m("2850") and b.status == "unpaid"


def test_partial():
    """部分收款：状态部分收款，待收减少"""
    b = bill("2850", "0", "0").pay(m("1000"))
    assert (b.paid, b.outstanding, b.status) == (m("1000"), m("1850"), "partial")


def test_settled_in_two_payments():
    """分两次收齐：状态已结清"""
    b = bill("2850", "0", "0").pay(m("1000")).pay(m("1850"))
    assert b.outstanding == 0 and b.status == "settled"


def test_overpay_rejected():
    """收款超过待收金额被拒绝"""
    with pytest.raises(ValueError, match="850"):
        bill("2850", "0", "2000").pay(m("900"))


def test_non_positive_rejected():
    """收款金额必须大于 0"""
    b = bill("2850", "0", "0")
    for amount in (m("0"), m("-1"), None):
        with pytest.raises(ValueError):
            b.pay(amount)


def test_settled_cannot_pay():
    """已结清的账单不能再收款"""
    with pytest.raises(ValueError):
        bill("2850", "0", "2850").pay(m("1"))


def test_discount_then_pay():
    """减免后再收齐剩余部分：已结清"""
    b = bill("2850", "0", "0").discount(m("50")).pay(m("2800"))
    assert b.status == "settled" and b.discount_amount == m("50")


def test_full_discount():
    """全额减免：一分没收也算已结清"""
    assert bill("2850", "0", "0").discount(m("2850")).status == "settled"


def test_discount_bounds():
    """减免不能超过 应收 - 已收，也不能为负"""
    b = bill("2850", "0", "2000")
    with pytest.raises(ValueError):
        b.discount(m("851"))
    with pytest.raises(ValueError):
        b.discount(m("-1"))
    assert b.discount(m("850")).status == "settled"


def test_reverse_payment():
    """作废一笔收款：已收回退，状态随之回到部分收款或待收"""
    partial = bill("2850", "0", "2850").reverse(m("1850"))
    assert partial.status == "partial"
    assert partial.reverse(m("1000")).status == "unpaid"


def test_reverse_bounds():
    """作废金额不能超过已收"""
    b = bill("2850", "0", "1000")
    with pytest.raises(ValueError):
        b.reverse(m("1000.01"))
    with pytest.raises(ValueError):
        b.reverse(m("0"))


def test_nulls_and_scale():
    """金额统一保留两位小数，空值按 0"""
    b = BillLedger(m("100"), None, None)
    assert b.outstanding == m("100.00")
    assert b.pay(m("33.333")).paid.as_tuple().exponent == -2
