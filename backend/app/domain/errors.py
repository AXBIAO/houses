"""仓储层抛出的业务错误，路由层统一映射为 HTTP 状态码。"""
from __future__ import annotations


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    """不存在，或不属于当前房东（两者对外不区分，避免泄露其他房东的数据是否存在）。"""
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Forbidden(DomainError):
    status_code = 403
