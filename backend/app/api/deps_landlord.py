"""房东后台的权限依赖：从登录账号解析所属房东，所有后台接口都以它限定数据范围。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from backend.app.core.auth import RequireUser


@dataclass(frozen=True)
class LandlordContext:
    landlord_id: int
    landlord_name: str
    user_id: int
    role: str

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


async def RequireLandlord(request: Request, user: dict[str, Any] = Depends(RequireUser)) -> LandlordContext:
    membership = await asyncio.to_thread(request.app.state.landlords.membership_for_user, user["user_id"])
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "当前账号不是房东成员")
    if membership["status"] != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "房东账号已被停用，请联系平台")
    return LandlordContext(membership["landlord_id"], membership["name"], user["user_id"], membership["role"])


async def RequireLandlordOwner(ctx: LandlordContext = Depends(RequireLandlord)) -> LandlordContext:
    if not ctx.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅房东主账号可操作")
    return ctx
