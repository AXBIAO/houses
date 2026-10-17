-- P4 房源订阅与通知。filters 存的就是 /api/listings 的查询参数（对象形式），匹配时复用同一套检索逻辑。

CREATE TABLE subscriptions (
    id             bigserial PRIMARY KEY,
    user_id        bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name           text        NOT NULL CHECK (length(name) BETWEEN 1 AND 30),
    filters        jsonb       NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(filters) = 'object'),
    email_enabled  boolean     NOT NULL DEFAULT false,
    active         boolean     NOT NULL DEFAULT true,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX subscriptions_user_idx ON subscriptions (user_id);
CREATE INDEX subscriptions_active_idx ON subscriptions (active) WHERE active;

-- 同一订阅对同一房源的同一事件只通知一次；降价按价格区分，再次降价会再通知
CREATE TABLE notifications (
    id               bigserial PRIMARY KEY,
    user_id          bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subscription_id  bigint      REFERENCES subscriptions (id) ON DELETE CASCADE,
    listing_id       bigint      NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    kind             text        NOT NULL CHECK (kind IN ('new', 'price_drop')),
    price            integer     NOT NULL DEFAULT 0,
    title            text        NOT NULL,
    body             text        NOT NULL DEFAULT '',
    read_at          timestamptz,
    emailed_at       timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subscription_id, listing_id, kind, price)
);
CREATE INDEX notifications_user_idx ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (user_id) WHERE read_at IS NULL;
