"""数据库行 → 前端 JSON：键名转 camelCase，Decimal 转 float。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return camelize(value)
    if isinstance(value, list):
        return [_value(v) for v in value]
    return value


def camelize(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_camel(k): _value(v) for k, v in row.items()}


def camelize_all(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [camelize(r) for r in rows]
