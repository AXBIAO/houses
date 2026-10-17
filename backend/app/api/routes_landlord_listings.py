"""房东后台：房源增删改、上下架、图片、不可租时段。"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status

from backend.app.api.deps_landlord import LandlordContext, RequireLandlord
from backend.app.api.schemas_landlord import BlockIn, ImageOrderIn, ListingIn, StatusIn
from backend.app.api.serialize import camelize, camelize_all
from backend.app.core.config import settings
from backend.app.core.media import MediaError, remove_public_file, save_listing_image
from backend.app.domain.errors import DomainError
from backend.app.services.notifier import match_listing

router = APIRouter(prefix="/api/landlord/listings", tags=["landlord"])


def _repo(request: Request):
    return request.app.state.listing_admin


async def _detail(request: Request, ctx: LandlordContext, listing_id: int) -> dict[str, Any]:
    return camelize(await asyncio.to_thread(_repo(request).get, ctx.landlord_id, listing_id))


@router.get("")
async def list_listings(
    request: Request,
    status_: Literal["draft", "published", "offline"] | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1, le=1000),
    pageSize: int = Query(20, ge=1, le=100),
    ctx: LandlordContext = Depends(RequireLandlord),
) -> dict[str, Any]:
    rows, total = await asyncio.to_thread(_repo(request).list, ctx.landlord_id, status=status_, keyword=(q or "").strip() or None,
                                          limit=pageSize, offset=(page - 1) * pageSize)
    return {"items": camelize_all(rows), "total": total, "page": page, "pageSize": pageSize}


@router.get("/{listing_id}")
async def get_listing(listing_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    return await _detail(request, ctx, listing_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_listing(body: ListingIn, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    listing_id = await asyncio.to_thread(_repo(request).create, ctx.landlord_id, body.to_db())
    return await _detail(request, ctx, listing_id)


@router.put("/{listing_id}")
async def update_listing(listing_id: int, body: ListingIn, request: Request, background: BackgroundTasks,
                         ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    change = await asyncio.to_thread(_repo(request).update, ctx.landlord_id, listing_id, body.to_db())
    if change.dropped:
        background.add_task(match_listing, request.app.state, listing_id, "price_drop", change.old_price)
    return await _detail(request, ctx, listing_id)


@router.post("/{listing_id}/status")
async def change_status(listing_id: int, body: StatusIn, request: Request, background: BackgroundTasks,
                        ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    await asyncio.to_thread(_repo(request).set_status, ctx.landlord_id, listing_id, body.status)
    if body.status == "published":
        # 响应先返回，订阅匹配与推送在后台进行
        background.add_task(match_listing, request.app.state, listing_id, "new")
    return await _detail(request, ctx, listing_id)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(listing_id: int, request: Request, ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    urls = await asyncio.to_thread(_repo(request).delete, ctx.landlord_id, listing_id)
    for url in urls:
        remove_public_file(url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- 图片 ----------------------------------------------------------------

@router.post("/{listing_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_image(listing_id: int, request: Request, file: UploadFile = File(...),
                       ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    repo = _repo(request)
    # 先确认归属与数量，避免把文件写进磁盘后才发现无权或已满
    if await asyncio.to_thread(repo.image_count, ctx.landlord_id, listing_id) >= settings.listing_max_images:
        raise HTTPException(status.HTTP_409_CONFLICT, f"每套房源最多 {settings.listing_max_images} 张图片")
    data = await file.read(settings.upload_max_bytes + 1)
    try:
        url = await asyncio.to_thread(save_listing_image, listing_id, data)
    except MediaError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    try:
        row = await asyncio.to_thread(repo.add_image, ctx.landlord_id, listing_id, url, settings.listing_max_images)
    except DomainError:
        remove_public_file(url)
        raise
    return camelize(row)


@router.put("/{listing_id}/images/order")
async def reorder_images(listing_id: int, body: ImageOrderIn, request: Request,
                         ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    await asyncio.to_thread(_repo(request).reorder_images, ctx.landlord_id, listing_id, body.imageIds)
    return await _detail(request, ctx, listing_id)


@router.delete("/{listing_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(listing_id: int, image_id: int, request: Request,
                       ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    url = await asyncio.to_thread(_repo(request).delete_image, ctx.landlord_id, listing_id, image_id)
    remove_public_file(url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- 不可租时段 ----------------------------------------------------------

@router.post("/{listing_id}/blocks", status_code=status.HTTP_201_CREATED)
async def add_block(listing_id: int, body: BlockIn, request: Request,
                    ctx: LandlordContext = Depends(RequireLandlord)) -> dict[str, Any]:
    row = await asyncio.to_thread(_repo(request).add_block, ctx.landlord_id, listing_id, body.start, body.end, body.note.strip())
    return camelize(row)


@router.delete("/{listing_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(listing_id: int, block_id: int, request: Request,
                       ctx: LandlordContext = Depends(RequireLandlord)) -> Response:
    await asyncio.to_thread(_repo(request).delete_block, ctx.landlord_id, listing_id, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
