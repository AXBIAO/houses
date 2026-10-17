"""仓储共用的小工具。"""
from __future__ import annotations

from typing import Any, Mapping


def set_clause(fields: Mapping[str, Any], allowed: frozenset[str]) -> tuple[str, list[Any]]:
    """按白名单生成 `col = %s, ...`；列名只来自白名单常量，值全部参数化。"""
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"不允许更新的字段: {sorted(unknown)}")
    columns = list(fields)
    return ", ".join(f"{c} = %s" for c in columns), [fields[c] for c in columns]


def like_pattern(keyword: str) -> str:
    escaped = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
