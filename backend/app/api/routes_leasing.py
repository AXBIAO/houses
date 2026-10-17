"""房东后台：租客、收费项目、租约（签约/修改/作废/退租）、抄表。"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from backend.app.api.deps_landlord import LandlordContext, RequireLandlord
from backend.app.api.schemas_leasing import CheckoutIn, FeeItemIn, LeaseMetaIn, LeaseSignIn, MeterIn, RenterIn
from backend.app.api.serialize import camelize, camelize_all
from backend.app.domain.billing import PlannedBill
from backend.app.repositories.checkout import ExtraCharge
from backend.app.repositories.leases import FeeChoice, SignInput

router = APIRouter(prefix="/api/landlord", tags=["leasing"])


def _state(request: Request):
    return request.app.state


def _today() -> date:
    return date.today()


# ---- 租客 ----------------------------------------------------------------

@router.get("/renters")
async def list_renters(request: Request, q: str | None = Query(None, max_length=30),
                       ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    rows = await asyncio.to_thread(_state(request).renters.list_renters, ctx.landlord_id, (q or "").strip() or None)
    return {"items": camelize_all(rows)}


@router.post("/renters", status_code=status.HTTP_201_CREATED)
async def create_renter(body: RenterIn, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).renters.create_renter, ctx.landlord_id, body.to_db()))


@router.put("/renters/{renter_id}")
async def update_renter(renter_id: int, body: RenterIn, request: Request,
                        ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).renters.update_renter, ctx.landlord_id, renter_id, body.to_db()))


@router.delete("/renters/{renter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_renter(renter_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    await asyncio.to_thread(_state(request).renters.delete_renter, ctx.landlord_id, renter_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- 收费项目 ------------------------------------------------------------

@router.get("/fee-items")
async def list_fee_items(request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return {"items": camelize_all(await asyncio.to_thread(_state(request).renters.list_fee_items, ctx.landlord_id))}


@router.post("/fee-items", status_code=status.HTTP_201_CREATED)
async def create_fee_item(body: FeeItemIn, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).renters.create_fee_item, ctx.landlord_id, body.to_db()))


@router.put("/fee-items/{item_id}")
async def update_fee_item(item_id: int, body: FeeItemIn, request: Request,
                          ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).renters.update_fee_item, ctx.landlord_id, item_id, body.to_db()))


@router.delete("/fee-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fee_item(item_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    await asyncio.to_thread(_state(request).renters.delete_fee_item, ctx.landlord_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- 租约 ----------------------------------------------------------------

def _sign_input(body: LeaseSignIn) -> SignInput:
    return SignInput(
        listing_id=body.listingId, renter_id=body.renterId,
        new_renter=body.newRenter.to_db() if body.newRenter else None,
        start_date=body.startDate, end_date=body.endDate, monthly_rent=body.monthlyRent, deposit=body.deposit,
        pay_cycle_months=body.payCycleMonths, advance_days=body.advanceDays, occupants=body.occupants,
        signed_date=body.signedDate, fees=tuple(FeeChoice(f.feeItemId, f.price) for f in body.fees),
        note=body.note.strip(), inquiry_id=body.inquiryId,
    )


def _planned(bill: PlannedBill) -> dict[str, Any]:
    return {
        "kind": bill.kind, "periodNo": bill.period_no, "periodStart": bill.period_start, "periodEnd": bill.period_end,
        "dueDate": bill.due_date, "totalAmount": bill.total_amount,
        "items": [{"name": i.item_name, "quantity": i.quantity, "unitPrice": i.unit_price, "amount": i.amount} for i in bill.items],
    }


@router.post("/leases/preview")
async def preview_lease(body: LeaseSignIn, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    """签约前预览将生成的账单（不落库）。"""
    bills = await asyncio.to_thread(_state(request).leases.preview, ctx.landlord_id, _sign_input(body))
    return camelize({"bills": [_planned(b) for b in bills], "total": sum(b.total_amount for b in bills)})


@router.post("/leases", status_code=status.HTTP_201_CREATED)
async def sign_lease(body: LeaseSignIn, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    repo = _state(request).leases
    lease_id = await asyncio.to_thread(repo.sign, ctx.landlord_id, ctx.user_id, _sign_input(body), today=_today())
    return camelize(await asyncio.to_thread(repo.get, ctx.landlord_id, lease_id, today=_today()))


@router.get("/leases")
async def list_leases(
    request: Request,
    status_: Literal["pending", "active", "expired", "checked_out", "void"] | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=40),
    expiring: bool = False,
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=100),
    ctx: LandlordContext = Depends(RequireLandlord),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_state(request).leases.list, ctx.landlord_id, status=status_,
                                          keyword=(q or "").strip() or None, expiring=expiring, today=_today(),
                                          limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}


@router.get("/leases/{lease_id}")
async def get_lease(lease_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).leases.get, ctx.landlord_id, lease_id, today=_today()))


@router.patch("/leases/{lease_id}")
async def update_lease(lease_id: int, body: LeaseMetaIn, request: Request,
                       ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    repo = _state(request).leases
    await asyncio.to_thread(repo.update_meta, ctx.landlord_id, lease_id, occupants=body.occupants,
                            signed_date=body.signedDate, note=body.note.strip())
    return camelize(await asyncio.to_thread(repo.get, ctx.landlord_id, lease_id, today=_today()))


@router.post("/leases/{lease_id}/void")
async def void_lease(lease_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    repo = _state(request).leases
    await asyncio.to_thread(repo.void, ctx.landlord_id, lease_id)
    return camelize(await asyncio.to_thread(repo.get, ctx.landlord_id, lease_id, today=_today()))


@router.post("/leases/{lease_id}/checkout")
async def checkout_lease(lease_id: int, body: CheckoutIn, request: Request,
                         ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    if body.checkoutDate > _today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "退租日期不能晚于今天")
    extras = tuple(ExtraCharge(e.name.strip(), e.amount) for e in body.extras)
    result = await asyncio.to_thread(_state(request).checkout.checkout, ctx.landlord_id, lease_id,
                                     checkout_date=body.checkoutDate, extras=extras, note=body.note.strip(), user_id=ctx.user_id)
    lease = await asyncio.to_thread(_state(request).leases.get, ctx.landlord_id, lease_id, today=_today())
    return {"result": camelize(result), "lease": camelize(lease)}


# ---- 抄表 ----------------------------------------------------------------

@router.get("/leases/{lease_id}/meter-last")
async def last_reading(lease_id: int, request: Request, feeItemId: int = Query(gt=0),
                       ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    row = await asyncio.to_thread(_state(request).meters.last_reading, ctx.landlord_id, lease_id, feeItemId)
    return {"last": camelize(row) if row else None}


@router.post("/leases/{lease_id}/meter-readings", status_code=status.HTTP_201_CREATED)
async def create_reading(lease_id: int, body: MeterIn, request: Request,
                         ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    if body.readDate > _today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "抄表日期不能晚于今天")
    row = await asyncio.to_thread(_state(request).meters.create, ctx.landlord_id, lease_id, fee_item_id=body.feeItemId,
                                  reading=body.reading, read_date=body.readDate, prev_reading=body.prevReading)
    return camelize(row)


@router.delete("/meter-readings/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reading(reading_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    await asyncio.to_thread(_state(request).meters.delete, ctx.landlord_id, reading_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
