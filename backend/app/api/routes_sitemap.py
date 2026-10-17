"""站点地图：公开页面 + 所有上架房源，供搜索引擎收录。"""
from __future__ import annotations

import asyncio
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request, Response

from backend.app.core.config import settings

router = APIRouter(tags=["seo"])

STATIC_PATHS = ("/", "/listings", "/map", "/ai", "/about")
MAX_URLS = 5000


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request) -> Response:
    base = settings.public_base_url.rstrip("/")
    rows = await asyncio.to_thread(request.app.state.listings.sitemap_entries, MAX_URLS)
    urls = [f"<url><loc>{escape(base + path)}</loc></url>" for path in STATIC_PATHS]
    for row in rows:
        loc = escape(f"{base}/listings/{row['id']}")
        urls.append(f"<url><loc>{loc}</loc><lastmod>{row['updated_at'].date().isoformat()}</lastmod></url>")
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    return Response(body, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/robots.txt", include_in_schema=False)
async def robots() -> Response:
    """按 PUBLIC_BASE_URL 生成，部署时不需要手改域名。后台页面不让搜索引擎抓取。"""
    base = settings.public_base_url.rstrip("/")
    body = "\n".join([
        "User-agent: *", "Allow: /", "Disallow: /landlord", "Disallow: /admin", "Disallow: /subscriptions", "Disallow: /api/",
        "", f"Sitemap: {base}/sitemap.xml", "",
    ])
    return Response(body, media_type="text/plain", headers={"Cache-Control": "public, max-age=3600"})
