"""房东后台：概览、小区、咨询、成员。房源管理见 routes_landlord_listings。"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from backend.app.api.deps_landlord import LandlordContext, RequireLandlord, RequireLandlordOwner
from backend.app.api.schemas_landlord import EstateIn, InquiryUpdateIn, MemberIn
from backend.app.api.serialize import camelize, camelize_all

router = APIRouter(prefix="/api/landlord", tags=["landlord"])


def _state(request: Request):
    return request.app.state


@router.get("/me")
async def me(ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return {"landlordId": ctx.landlord_id, "name": ctx.landlord_name, "role": ctx.role}


@router.get("/overview")
async def overview(request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return await asyncio.to_thread(_state(request).landlords.overview, ctx.landlord_id)


# ---- 小区 ----------------------------------------------------------------

@router.get("/estates")
async def list_estates(request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    rows = await asyncio.to_thread(_state(request).estates.list, ctx.landlord_id)
    return {"items": camelize_all(rows)}


@router.post("/estates", status_code=status.HTTP_201_CREATED)
async def create_estate(body: EstateIn, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).estates.create, ctx.landlord_id, body.to_db()))


@router.put("/estates/{estate_id}")
async def update_estate(estate_id: int, body: EstateIn, request: Request,
                        ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).estates.update, ctx.landlord_id, estate_id, body.to_db()))


@router.delete("/estates/{estate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_estate(estate_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    await asyncio.to_thread(_state(request).estates.delete, ctx.landlord_id, estate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- 咨询 ----------------------------------------------------------------

@router.get("/inquiries")
async def list_inquiries(
    request: Request,
    status_: Literal["new", "contacted", "closed"] | None = Query(None, alias="status"),
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=100),
    ctx: LandlordContext = Depends(RequireLandlord),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_state(request).inquiries.list, ctx.landlord_id, status=status_,
                                          limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}


@router.patch("/inquiries/{inquiry_id}")
async def update_inquiry(inquiry_id: int, body: InquiryUpdateIn, request: Request,
                         ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    note = body.note.strip() if body.note is not None else None
    row = await asyncio.to_thread(_state(request).inquiries.update, ctx.landlord_id, inquiry_id, status=body.status, note=note)
    return camelize(row)


# ---- 成员 ----------------------------------------------------------------

@router.get("/members")
async def list_members(request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    rows = await asyncio.to_thread(_state(request).landlords.list_members, ctx.landlord_id)
    return {"items": camelize_all(rows)}


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def add_member(body: MemberIn, request: Request, ctx: LandlordContext = Depends(RequireLandlordOwner)) -> dict[str, Any]:
    user = await asyncio.to_thread(_state(request).users.get_login_record, body.account.strip())
    if user is None or user.get("disabled"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在，请让对方先注册")
    await asyncio.to_thread(_state(request).landlords.add_member, ctx.landlord_id, user["id"], body.role)
    return {"userId": user["id"], "role": body.role}


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(user_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlordOwner)) -> Response:
    await asyncio.to_thread(_state(request).landlords.remove_member, ctx.landlord_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
