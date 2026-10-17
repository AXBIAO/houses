-- 后台可修改的系统设置（大模型、邮件等）。密钥字段在应用层加密后再存入 value。
CREATE TABLE app_settings (
    key         text        PRIMARY KEY,
    value       jsonb       NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(value) = 'object'),
    updated_by  bigint      REFERENCES users (id) ON DELETE SET NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
