"""平台管理：开通/停用房东、房源审核。仅平台管理员与超级管理员。"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.api.schemas_landlord import LandlordCreateIn, LandlordUpdateIn, ModerateIn
from backend.app.api.serialize import camelize, camelize_all
from backend.app.core.auth import RequirePlatformAdmin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(RequirePlatformAdmin)])


def _state(request: Request):
    return request.app.state


@router.get("/landlords")
async def list_landlords(
    request: Request,
    q: str | None = Query(None, max_length=40),
    status_: Literal["active", "disabled"] | None = Query(None, alias="status"),
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_state(request).landlords.list_landlords, keyword=(q or "").strip() or None,
                                          status=status_, limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}


@router.post("/landlords", status_code=status.HTTP_201_CREATED)
async def create_landlord(body: LandlordCreateIn, request: Request) -> dict[str, Any]:
    owner = await asyncio.to_thread(_state(request).users.get_login_record, body.ownerAccount.strip())
    if owner is None or owner.get("disabled"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "主账号不存在，请让房东先注册")
    row = await asyncio.to_thread(_state(request).landlords.create, name=body.name.strip(), contact_name=body.contactName,
                                  contact_phone=body.contactPhone, owner_user_id=owner["id"])
    return camelize(row)


@router.patch("/landlords/{landlord_id}")
async def update_landlord(landlord_id: int, body: LandlordUpdateIn, request: Request) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_state(request).landlords.update, landlord_id, body.to_db()))


@router.get("/listings")
async def list_listings(
    request: Request,
    landlordId: int | None = Query(None, gt=0),
    status_: Literal["draft", "published", "offline"] | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_state(request).listing_admin.list, landlordId, status=status_,
                                          keyword=(q or "").strip() or None, limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}


@router.patch("/listings/{listing_id}")
async def moderate_listing(listing_id: int, body: ModerateIn, request: Request) -> dict[str, bool]:
    if body.status is None and body.recommended is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "没有要修改的内容")
    await asyncio.to_thread(_state(request).listing_admin.moderate, listing_id, status=body.status, recommended=body.recommended)
    return {"ok": True}
