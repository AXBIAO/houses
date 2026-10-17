"""账号仓储（PostgreSQL）。"""
from __future__ import annotations

from typing import Any

from backend.app.core.postgres_database import PostgresDatabaseLifecycle

_PUBLIC_COLUMNS = "id, email, phone, username, role, disabled, pwd_ver, created_at, last_login_at"


class UserRepository:
    def __init__(self, database: PostgresDatabaseLifecycle) -> None:
        self._db = database

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._db.transaction() as conn:
            return conn.execute(f"SELECT {_PUBLIC_COLUMNS} FROM users WHERE id = %s", (user_id,)).fetchone()

    def get_login_record(self, account: str) -> dict[str, Any] | None:
        """按邮箱（不区分大小写）或手机号查找，含密码哈希，仅供登录校验。"""
        with self._db.transaction() as conn:
            return conn.execute(
                f"SELECT {_PUBLIC_COLUMNS}, password_hash FROM users "
                "WHERE lower(email) = lower(%s) OR phone = %s LIMIT 1",
                (account, account),
            ).fetchone()

    def exists(self, *, email: str | None, phone: str | None) -> bool:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE (%s::text IS NOT NULL AND lower(email) = lower(%s)) "
                "OR (%s::text IS NOT NULL AND phone = %s) LIMIT 1",
                (email, email, phone, phone),
            ).fetchone()
            return row is not None

    def create_user(self, *, email: str | None, phone: str | None, username: str, password_hash: str,
                    role: str = "user") -> dict[str, Any]:
        with self._db.transaction() as conn:
            return conn.execute(
                "INSERT INTO users (email, phone, username, password_hash, role) VALUES (%s, %s, %s, %s, %s) "
                f"RETURNING {_PUBLIC_COLUMNS}",
                (email, phone, username, password_hash, role),
            ).fetchone()

    def touch_login(self, user_id: int) -> None:
        with self._db.transaction() as conn:
            conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user_id,))

    def get_password_hash(self, user_id: int) -> str | None:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,)).fetchone()
        return row["password_hash"] if row else None

    def change_password(self, user_id: int, password_hash: str) -> dict[str, Any]:
        """改密同时递增 pwd_ver，其他设备上的旧登录立即失效。"""
        with self._db.transaction() as conn:
            return conn.execute(
                f"UPDATE users SET password_hash = %s, pwd_ver = pwd_ver + 1 WHERE id = %s RETURNING {_PUBLIC_COLUMNS}",
                (password_hash, user_id),
            ).fetchone()

    def has_role(self, role: str) -> bool:
        with self._db.transaction() as conn:
            return conn.execute("SELECT 1 FROM users WHERE role = %s LIMIT 1", (role,)).fetchone() is not None
