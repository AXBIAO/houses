"""房源图片的本地存储。按文件头识别真实格式，不信任文件名与 Content-Type。"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from backend.app.core.config import settings

logger = logging.getLogger("houses.media")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PREFIX = "/uploads/"


class MediaError(ValueError):
    pass


def upload_root() -> Path:
    root = Path(settings.upload_dir)
    return (root if root.is_absolute() else PROJECT_ROOT / root).resolve()


def detect_image_ext(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_listing_image(listing_id: int, data: bytes) -> str:
    if not data:
        raise MediaError("文件为空")
    if len(data) > settings.upload_max_bytes:
        raise MediaError(f"图片不能超过 {settings.upload_max_bytes // (1024 * 1024)} MB")
    ext = detect_image_ext(data)
    if ext is None:
        raise MediaError("只支持 JPG、PNG、WebP 图片")
    relative = Path("listings") / str(listing_id) / f"{uuid.uuid4().hex}.{ext}"
    target = upload_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return PUBLIC_PREFIX + relative.as_posix()


def remove_public_file(url: str) -> None:
    """只删除 upload_root 之内的文件；外链或越界路径直接忽略。"""
    if not url.startswith(PUBLIC_PREFIX):
        return
    root = upload_root()
    target = (root / url[len(PUBLIC_PREFIX):]).resolve()
    if root not in target.parents:
        logger.warning("拒绝删除越界路径 %s", url)
        return
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("删除图片失败 %s: %s", target, exc)
