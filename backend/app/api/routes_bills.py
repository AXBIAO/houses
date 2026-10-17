"""房东后台：账单、登记收款、减免、收款流水。只记账，不对接任何支付通道。"""
from __future__ import annotations

import asyncio
import calendar
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.api.deps_landlord import LandlordContext, RequireLandlord
from backend.app.api.schemas_leasing import DiscountIn, PayIn
from backend.app.api.serialize import camelize, camelize_all

router = APIRouter(prefix="/api/landlord", tags=["bills"])


def _repo(request: Request):
    return request.app.state.bills


@router.get("/bills/summary")
async def bills_summary(request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    today = date.today()
    start = today.replace(day=1)
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    row = await asyncio.to_thread(_repo(request).summary, ctx.landlord_id, today=today, month_start=start, month_end=end)
    return camelize(row)


@router.get("/bills")
async def list_bills(
    request: Request,
    status_: Literal["open", "unpaid", "partial", "settled", "void"] | None = Query(None, alias="status"),
    overdue: bool = False,
    leaseId: int | None = Query(None, gt=0),
    q: str | None = Query(None, max_length=40),
    dueFrom: date | None = None,
    dueTo: date | None = None,
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(30, ge=1, le=200),
    ctx: LandlordContext = Depends(RequireLandlord),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_repo(request).list, ctx.landlord_id, status=status_, overdue=overdue,
                                          lease_id=leaseId, keyword=(q or "").strip() or None, due_from=dueFrom,
                                          due_to=dueTo, today=date.today(), limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}


@router.get("/bills/{bill_id}")
async def get_bill(bill_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_repo(request).get, ctx.landlord_id, bill_id, today=date.today()))


@router.post("/bills/{bill_id}/payments", status_code=status.HTTP_201_CREATED)
async def record_payment(bill_id: int, body: PayIn, request: Request,
                         ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    """登记一笔线下收款。"""
    paid_on = body.paidOn or date.today()
    if paid_on > date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "收款日期不能晚于今天")
    await asyncio.to_thread(_repo(request).pay, ctx.landlord_id, bill_id, amount=body.amount, method=body.method,
                            paid_on=paid_on, note=body.note.strip(), user_id=ctx.user_id)
    return camelize(await asyncio.to_thread(_repo(request).get, ctx.landlord_id, bill_id, today=date.today()))


@router.put("/bills/{bill_id}/discount")
async def set_discount(bill_id: int, body: DiscountIn, request: Request,
                       ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    note = body.note.strip() if body.note is not None else None
    await asyncio.to_thread(_repo(request).discount, ctx.landlord_id, bill_id, body.amount, note)
    return camelize(await asyncio.to_thread(_repo(request).get, ctx.landlord_id, bill_id, today=date.today()))


@router.post("/payments/{payment_id}/void")
async def void_payment(payment_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, bool]:
    await asyncio.to_thread(_repo(request).void_payment, ctx.landlord_id, payment_id)
    return {"ok": True}


@router.get("/payments")
async def list_payments(
    request: Request,
    method: Literal["cash", "wechat", "alipay", "bank", "other", "deposit_offset", "deposit_refund"] | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(30, ge=1, le=200),
    ctx: LandlordContext = Depends(RequireLandlord),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_repo(request).payments, ctx.landlord_id, method=method, date_from=dateFrom,
                                          date_to=dateTo, limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}
