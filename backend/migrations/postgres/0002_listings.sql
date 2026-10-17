-- P1 房源与前台找房。landlord_id 贯穿各表，P2 的多房东隔离按它过滤。

CREATE TABLE landlords (
    id             bigserial PRIMARY KEY,
    name           text        NOT NULL,
    contact_name   text,
    contact_phone  text,
    status         text        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

-- 小区 / 项目
CREATE TABLE estates (
    id           bigserial PRIMARY KEY,
    landlord_id  bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    name         text          NOT NULL,
    city         text          NOT NULL,
    district     text          NOT NULL,
    address      text          NOT NULL DEFAULT '',
    lat          numeric(9, 6) NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lng          numeric(9, 6) NOT NULL CHECK (lng BETWEEN -180 AND 180),
    created_at   timestamptz   NOT NULL DEFAULT now(),
    updated_at   timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX estates_landlord_idx ON estates (landlord_id);

-- 对外展示与出租的最小单元：整套（长租/短租）或合租中的一间
CREATE TABLE listings (
    id              bigserial PRIMARY KEY,
    landlord_id     bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    estate_id       bigint        NOT NULL REFERENCES estates (id) ON DELETE RESTRICT,
    building        text          NOT NULL DEFAULT '',
    unit_no         text          NOT NULL DEFAULT '',
    rent_type       text          NOT NULL CHECK (rent_type IN ('long', 'short', 'shared')),
    title           text          NOT NULL CHECK (length(title) BETWEEN 1 AND 80),
    description     text          NOT NULL DEFAULT '',
    bedrooms        smallint      NOT NULL DEFAULT 1 CHECK (bedrooms BETWEEN 0 AND 20),
    halls           smallint      NOT NULL DEFAULT 0 CHECK (halls BETWEEN 0 AND 10),
    baths           smallint      NOT NULL DEFAULT 1 CHECK (baths BETWEEN 0 AND 10),
    area            numeric(7, 2) NOT NULL CHECK (area > 0),
    floor           smallint,
    total_floors    smallint,
    orientation     text          NOT NULL DEFAULT '',
    -- 长租/合租按月价，短租按晚价；同一套房两种价都填可同时参与两类筛选的展示
    price_month     integer       CHECK (price_month > 0),
    price_night     integer       CHECK (price_night > 0),
    deposit_months  smallint      NOT NULL DEFAULT 1 CHECK (deposit_months BETWEEN 0 AND 12),
    min_months      smallint      NOT NULL DEFAULT 1 CHECK (min_months BETWEEN 1 AND 60),
    min_nights      smallint      NOT NULL DEFAULT 1 CHECK (min_nights BETWEEN 1 AND 365),
    tags            text[]        NOT NULL DEFAULT '{}',
    cover_url       text,
    status          text          NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'offline')),
    recommended     boolean       NOT NULL DEFAULT false,
    available_from  date,
    published_at    timestamptz,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    updated_at      timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT listings_price_by_type CHECK (
        (rent_type = 'short' AND price_night IS NOT NULL) OR (rent_type <> 'short' AND price_month IS NOT NULL)
    ),
    CONSTRAINT listings_published_at CHECK (status <> 'published' OR published_at IS NOT NULL)
);
CREATE INDEX listings_public_idx ON listings (status, rent_type, published_at DESC);
CREATE INDEX listings_landlord_idx ON listings (landlord_id);
CREATE INDEX listings_estate_idx ON listings (estate_id);
CREATE INDEX listings_tags_idx ON listings USING gin (tags);

CREATE TABLE listing_images (
    id          bigserial PRIMARY KEY,
    listing_id  bigint      NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    url         text        NOT NULL,
    sort        smallint    NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX listing_images_listing_idx ON listing_images (listing_id, sort);

-- 不可租时段，半开区间 [start_date, end_date)。P3 签约/短租预订会写入 kind=lease/booking
CREATE TABLE listing_unavailability (
    id          bigserial PRIMARY KEY,
    listing_id  bigint      NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    start_date  date        NOT NULL,
    end_date    date        NOT NULL,
    kind        text        NOT NULL DEFAULT 'block' CHECK (kind IN ('lease', 'booking', 'block')),
    note        text        NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (end_date > start_date)
);
CREATE INDEX listing_unavailability_idx ON listing_unavailability (listing_id, start_date, end_date);

-- 租客无账号也可咨询；user_id 仅在登录时记录
CREATE TABLE listing_inquiries (
    id           bigserial PRIMARY KEY,
    listing_id   bigint      NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    landlord_id  bigint      NOT NULL REFERENCES landlords (id) ON DELETE CASCADE,
    user_id      bigint      REFERENCES users (id) ON DELETE SET NULL,
    name         text        NOT NULL,
    phone        text        NOT NULL,
    message      text        NOT NULL DEFAULT '',
    move_in      date,
    move_out     date,
    client_ip    text,
    status       text        NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'closed')),
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX listing_inquiries_landlord_idx ON listing_inquiries (landlord_id, status, created_at DESC);
