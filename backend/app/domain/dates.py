"""日期工具。"""
from __future__ import annotations

import calendar
from datetime import date


def add_months(start: date, months: int) -> date:
    """按自然月推算，月末对齐（1/31 + 1 月 = 2/28 或 2/29），与 Java LocalDate.plusMonths 一致。"""
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
