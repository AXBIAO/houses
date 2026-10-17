-- Houses 0001：账号
-- 访客注册后为 user（租客）；平台角色 platform_admin / superadmin；房东身份由租户成员表（后续迁移）决定。

CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT,
    phone           TEXT,
    username        TEXT        NOT NULL,
    password_hash   TEXT        NOT NULL,
    role            TEXT        NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'platform_admin', 'superadmin')),
    disabled        BOOLEAN     NOT NULL DEFAULT FALSE,
    -- 改密时递增，签入 JWT；不一致即视为旧 token
    pwd_ver         INTEGER     NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ,
    CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- 邮箱不区分大小写唯一；手机号唯一
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone ON users (phone) WHERE phone IS NOT NULL;
