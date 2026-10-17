"""出账与账本的纯计算（不访问数据库），移植自 ruoyi 版 BillPlanner / BillLedger，规则与单测保持一致。

平台只记账不收钱：这里的「收款」只是房东登记的金额，不涉及任何支付通道。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from backend.app.domain.dates import add_months

BillKind = Literal["rent", "deposit", "settlement", "other"]
BillStatus = Literal["unpaid", "partial", "settled", "void"]

DAYS_PER_MONTH = 30
MAX_PERIODS = 240
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value if value is not None else 0).quantize(CENT, rounding=ROUND_HALF_UP)


def _div2(numerator: Decimal, denominator: int) -> Decimal:
    return (numerator / Decimal(denominator)).quantize(CENT, rounding=ROUND_HALF_UP)


# ---- 出账 -----------------------------------------------------------------

@dataclass(frozen=True)
class FixedFee:
    """签约时确定的固定费用。amount 为每月金额；一次性费用时为总金额，只计入第一期。"""
    item_id: int | None
    item_name: str
    amount: Decimal
    one_time: bool = False


@dataclass(frozen=True)
class LeaseTerms:
    start_date: date
    end_date: date  # 含当天
    monthly_rent: Decimal
    deposit: Decimal | None
    pay_cycle_months: int
    advance_days: int = 0
    fees: tuple[FixedFee, ...] = ()


@dataclass(frozen=True)
class PlannedItem:
    item_id: int | None
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class PlannedBill:
    kind: BillKind
    period_no: int | None
    period_start: date
    period_end: date
    due_date: date
    items: tuple[PlannedItem, ...]

    @property
    def total_amount(self) -> Decimal:
        return sum((i.amount for i in self.items), ZERO)


@dataclass(frozen=True)
class _Span:
    """一个账期内的计费时长：整月数 + 零头天数。"""
    months: int
    days: int

    def quantity(self) -> Decimal:
        return money(Decimal(self.months) + _div2(Decimal(self.days), DAYS_PER_MONTH))

    def charge(self, monthly: Decimal) -> Decimal:
        return money(monthly * self.months + _div2(monthly * self.days, DAYS_PER_MONTH))


def _validate(t: LeaseTerms) -> None:
    if t.start_date is None or t.end_date is None:
        raise ValueError("起租日和到期日不能为空")
    if t.end_date < t.start_date:
        raise ValueError("到期日不能早于起租日")
    if t.pay_cycle_months < 1:
        raise ValueError("付款周期至少为 1 个月")
    if t.monthly_rent is None or t.monthly_rent < 0:
        raise ValueError("月租金不能为空或负数")
    if t.advance_days < 0:
        raise ValueError("提前收租天数不能为负数")
    if t.deposit is not None and t.deposit < 0:
        raise ValueError("押金不能为负数")
    for fee in t.fees:
        if fee.amount is None or fee.amount < 0:
            raise ValueError(f"费用金额不能为空或负数：{fee.item_name}")


def _span(lease_start: date, offset: int, cycle: int, period_end: date) -> _Span:
    months = 0
    while months < cycle and not add_months(lease_start, offset + months + 1) - timedelta(days=1) > period_end:
        months += 1
    remainder_start = add_months(lease_start, offset + months)
    days = 0 if remainder_start > period_end else (period_end - remainder_start).days + 1
    return _Span(months, days)


def plan_bills(terms: LeaseTerms) -> list[PlannedBill]:
    """第 k 期开始日 = 起租日 + k×周期 个月（每次都从起租日推算，月末不越推越早）；
    最后一期零头天数按 月租/30 计；应收日 = 账期开始日 - 提前天数；一次性费用只进第一期。"""
    _validate(terms)
    bills: list[PlannedBill] = []
    if terms.deposit is not None and terms.deposit > 0:
        deposit = money(terms.deposit)
        bills.append(PlannedBill("deposit", None, terms.start_date, terms.end_date, terms.start_date,
                                 (PlannedItem(None, "押金", Decimal("1.00"), deposit, deposit),)))
    cycle = terms.pay_cycle_months
    k = 0
    while True:
        offset = k * cycle
        period_start = add_months(terms.start_date, offset)
        if period_start > terms.end_date:
            break
        if k >= MAX_PERIODS:
            raise ValueError("账期过多，请检查起止日期和付款周期")
        full_end = add_months(terms.start_date, offset + cycle) - timedelta(days=1)
        period_end = min(full_end, terms.end_date)
        span = _span(terms.start_date, offset, cycle, period_end)
        bills.append(_rent_bill(terms, k + 1, period_start, period_end, span))
        k += 1
    return bills


def _rent_bill(t: LeaseTerms, period_no: int, start: date, end: date, span: _Span) -> PlannedBill:
    items = [PlannedItem(None, "租金", span.quantity(), money(t.monthly_rent), span.charge(t.monthly_rent))]
    items += [PlannedItem(f.item_id, f.item_name, span.quantity(), money(f.amount), span.charge(f.amount))
              for f in t.fees if not f.one_time]
    if period_no == 1:
        items += [PlannedItem(f.item_id, f.item_name, Decimal("1.00"), money(f.amount), money(f.amount))
                  for f in t.fees if f.one_time]
    return PlannedBill("rent", period_no, start, end, start - timedelta(days=t.advance_days), tuple(items))


# ---- 账本 -----------------------------------------------------------------

@dataclass(frozen=True)
class BillLedger:
    """单张账单的金额账本（不可变）：每次收款、减免、冲正都返回新对象，校验失败抛 ValueError。"""
    total_amount: Decimal
    discount_amount: Decimal = field(default=ZERO)
    paid: Decimal = field(default=ZERO)

    def __post_init__(self) -> None:
        object.__setattr__(self, "total_amount", money(self.total_amount))
        object.__setattr__(self, "discount_amount", money(self.discount_amount))
        object.__setattr__(self, "paid", money(self.paid))

    @property
    def outstanding(self) -> Decimal:
        """待收 = 应收 - 减免 - 已收，最小为 0。"""
        left = self.total_amount - self.discount_amount - self.paid
        return ZERO if left < 0 else left

    @property
    def status(self) -> BillStatus:
        if self.outstanding == 0:
            return "settled"
        return "partial" if self.paid > 0 else "unpaid"

    def pay(self, amount: Decimal | None) -> "BillLedger":
        value = _require_positive(amount, "收款金额")
        if self.outstanding == 0:
            raise ValueError("账单已结清，不能再收款")
        if value > self.outstanding:
            raise ValueError(f"收款金额不能超过待收金额 {self.outstanding}")
        return replace(self, paid=self.paid + value)

    def discount(self, amount: Decimal | None) -> "BillLedger":
        """设置减免总额（不累加），不超过 应收 - 已收。"""
        value = money(amount)
        if value < 0:
            raise ValueError("减免金额不能为负数")
        ceiling = self.total_amount - self.paid
        if value > ceiling:
            raise ValueError(f"减免金额不能超过 应收 - 已收 = {ceiling}")
        return replace(self, discount_amount=value)

    def reverse(self, amount: Decimal | None) -> "BillLedger":
        """作废一笔收款：已收扣回。"""
        value = _require_positive(amount, "作废金额")
        if value > self.paid:
            raise ValueError(f"作废金额不能超过已收金额 {self.paid}")
        return replace(self, paid=self.paid - value)


def _require_positive(amount: Decimal | None, name: str) -> Decimal:
    if amount is None or Decimal(amount) <= 0:
        raise ValueError(f"{name}必须大于 0")
    return money(amount)
