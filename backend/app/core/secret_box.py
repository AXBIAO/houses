"""后台设置里的密钥（大模型 API Key、SMTP 密码）加密存库。

密钥由 JWT_SECRET_KEY 派生：更换 JWT_SECRET_KEY 后旧密文无法解密，需要在后台重新填写一次。
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config import settings

_PURPOSE = b"houses:app-settings:v1"


def _fernet() -> Fernet:
    digest = hashlib.sha256(_PURPOSE + settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str | None:
    """解密失败（例如更换过 JWT_SECRET_KEY）返回 None，调用方按「未设置」处理。"""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def tail(secret: str | None) -> str | None:
    """只给前端展示末 4 位。"""
    return secret[-4:] if secret and len(secret) >= 8 else ("****" if secret else None)
