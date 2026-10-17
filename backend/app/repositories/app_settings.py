"""后台系统设置（键值，值为 JSON 对象）。"""
from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from backend.app.core.postgres_database import PostgresDatabaseLifecycle


class AppSettingsRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def get(self, key: str) -> dict[str, Any] | None:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key = %s", (key,)).fetchone()
        return row["value"] if row else None

    def put(self, key: str, value: dict[str, Any], user_id: int | None) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = now()",
                (key, Jsonb(value), user_id),
            )

    def delete(self, key: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM app_settings WHERE key = %s", (key,))
