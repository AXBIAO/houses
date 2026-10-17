-- P3 出租与收租（只记账）。平台不接任何支付通道：payments 只是房东手动登记的流水。
-- 财务表（bills / bill_items / payments）只作废不删除。金额 numeric(12,2)，单价 numeric(10,4)。

-- 租客资料：只存联系所需信息；证件只留末 4 位用于核对，不存完整证件号
CREATE TABLE renters (
    id            bigserial PRIMARY KEY,
    landlord_id   bigint      NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    name          text        NOT NULL CHECK (length(name) BETWEEN 1 AND 30),
    phone         text        NOT NULL,
    id_card_tail  text        CHECK (id_card_tail ~ '^[0-9Xx]{4}$'),
    note          text        NOT NULL DEFAULT '',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX renters_landlord_idx ON renters (landlord_id, id DESC);

-- 房东自定义收费项目：fixed 每月固定、one_time 一次性、metered 按表计量（水电燃气）
CREATE TABLE fee_items (
    id             bigserial PRIMARY KEY,
    landlord_id    bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    name           text          NOT NULL CHECK (length(name) BETWEEN 1 AND 20),
    kind           text          NOT NULL CHECK (kind IN ('fixed', 'one_time', 'metered')),
    default_price  numeric(10,4) NOT NULL DEFAULT 0 CHECK (default_price >= 0),
    unit           text          NOT NULL DEFAULT '',
    active         boolean       NOT NULL DEFAULT true,
    created_at     timestamptz   NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX fee_items_name_uidx ON fee_items (landlord_id, name);

CREATE TABLE leases (
    id                 bigserial PRIMARY KEY,
    landlord_id        bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    listing_id         bigint        NOT NULL REFERENCES listings (id) ON DELETE RESTRICT,
    renter_id          bigint        NOT NULL REFERENCES renters (id) ON DELETE RESTRICT,
    lease_no           text          UNIQUE,
    start_date         date          NOT NULL,
    end_date           date          NOT NULL,
    monthly_rent       numeric(12,2) NOT NULL CHECK (monthly_rent >= 0),
    deposit            numeric(12,2) NOT NULL DEFAULT 0 CHECK (deposit >= 0),
    pay_cycle_months   smallint      NOT NULL CHECK (pay_cycle_months BETWEEN 1 AND 12),
    advance_days       smallint      NOT NULL DEFAULT 0 CHECK (advance_days BETWEEN 0 AND 60),
    occupants          smallint      NOT NULL DEFAULT 1 CHECK (occupants BETWEEN 1 AND 20),
    signed_date        date,
    status             text          NOT NULL CHECK (status IN ('pending', 'active', 'expired', 'checked_out', 'void')),
    checkout_date      date,
    checkout_note      text          NOT NULL DEFAULT '',
    deposit_offset     numeric(12,2) NOT NULL DEFAULT 0,
    deposit_refund     numeric(12,2) NOT NULL DEFAULT 0,
    inquiry_id         bigint        REFERENCES listing_inquiries (id) ON DELETE SET NULL,
    unavailability_id  bigint        REFERENCES listing_unavailability (id) ON DELETE SET NULL,
    note               text          NOT NULL DEFAULT '',
    created_by         bigint        REFERENCES users (id) ON DELETE SET NULL,
    created_at         timestamptz   NOT NULL DEFAULT now(),
    updated_at         timestamptz   NOT NULL DEFAULT now(),
    CHECK (end_date >= start_date),
    CHECK (end_date <= start_date + interval '10 years'),
    CHECK (status <> 'checked_out' OR checkout_date IS NOT NULL)
);
CREATE INDEX leases_landlord_idx ON leases (landlord_id, status, end_date);
CREATE INDEX leases_listing_idx ON leases (listing_id, status);
CREATE INDEX leases_renter_idx ON leases (renter_id);

-- 签约时带出的费用（名称与价格存快照，之后改收费项目不影响已签租约）
CREATE TABLE lease_fees (
    id           bigserial PRIMARY KEY,
    lease_id     bigint        NOT NULL REFERENCES leases (id) ON DELETE CASCADE,
    fee_item_id  bigint        NOT NULL REFERENCES fee_items (id) ON DELETE RESTRICT,
    name         text          NOT NULL,
    kind         text          NOT NULL CHECK (kind IN ('fixed', 'one_time', 'metered')),
    price        numeric(10,4) NOT NULL CHECK (price >= 0),
    UNIQUE (lease_id, fee_item_id)
);

CREATE TABLE bills (
    id               bigserial PRIMARY KEY,
    landlord_id      bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    lease_id         bigint        NOT NULL REFERENCES leases (id) ON DELETE RESTRICT,
    bill_no          text          UNIQUE,
    kind             text          NOT NULL CHECK (kind IN ('rent', 'deposit', 'settlement', 'other')),
    period_no        smallint,
    period_start     date,
    period_end       date,
    due_date         date          NOT NULL,
    total_amount     numeric(12,2) NOT NULL CHECK (total_amount >= 0),
    discount_amount  numeric(12,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    paid_amount      numeric(12,2) NOT NULL DEFAULT 0,
    status           text          NOT NULL DEFAULT 'unpaid' CHECK (status IN ('unpaid', 'partial', 'settled', 'void')),
    settled_at       timestamptz,
    note             text          NOT NULL DEFAULT '',
    created_at       timestamptz   NOT NULL DEFAULT now(),
    updated_at       timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX bills_landlord_idx ON bills (landlord_id, status, due_date);
CREATE INDEX bills_lease_idx ON bills (lease_id, kind, period_no);

-- 抄表：读数属于房间（listing），费用记入租约账单
CREATE TABLE meter_readings (
    id            bigserial PRIMARY KEY,
    landlord_id   bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    lease_id      bigint        NOT NULL REFERENCES leases (id) ON DELETE RESTRICT,
    listing_id    bigint        NOT NULL REFERENCES listings (id) ON DELETE RESTRICT,
    fee_item_id   bigint        NOT NULL REFERENCES fee_items (id) ON DELETE RESTRICT,
    prev_reading  numeric(12,2) NOT NULL CHECK (prev_reading >= 0),
    reading       numeric(12,2) NOT NULL,
    read_date     date          NOT NULL,
    usage         numeric(12,2) NOT NULL CHECK (usage >= 0),
    unit_price    numeric(10,4) NOT NULL CHECK (unit_price >= 0),
    amount        numeric(12,2) NOT NULL CHECK (amount >= 0),
    bill_id       bigint        REFERENCES bills (id) ON DELETE RESTRICT,
    created_at    timestamptz   NOT NULL DEFAULT now(),
    CHECK (reading >= prev_reading)
);
CREATE INDEX meter_readings_listing_idx ON meter_readings (listing_id, fee_item_id, read_date DESC, id DESC);
CREATE INDEX meter_readings_lease_idx ON meter_readings (lease_id);

CREATE TABLE bill_items (
    id                bigserial PRIMARY KEY,
    bill_id           bigint        NOT NULL REFERENCES bills (id) ON DELETE RESTRICT,
    fee_item_id       bigint        REFERENCES fee_items (id) ON DELETE RESTRICT,
    meter_reading_id  bigint        REFERENCES meter_readings (id) ON DELETE SET NULL,
    name              text          NOT NULL,
    quantity          numeric(10,2) NOT NULL DEFAULT 1,
    unit_price        numeric(10,4) NOT NULL DEFAULT 0,
    amount            numeric(12,2) NOT NULL CHECK (amount >= 0)
);
CREATE INDEX bill_items_bill_idx ON bill_items (bill_id);

-- 收款流水：房东登记的线下收款。退押金记负数；押金抵扣由退租结算自动生成
CREATE TABLE payments (
    id           bigserial PRIMARY KEY,
    landlord_id  bigint        NOT NULL REFERENCES landlords (id) ON DELETE RESTRICT,
    bill_id      bigint        NOT NULL REFERENCES bills (id) ON DELETE RESTRICT,
    amount       numeric(12,2) NOT NULL CHECK (amount <> 0),
    method       text          NOT NULL CHECK (method IN ('cash', 'wechat', 'alipay', 'bank', 'other', 'deposit_offset', 'deposit_refund')),
    paid_on      date          NOT NULL,
    note         text          NOT NULL DEFAULT '',
    status       text          NOT NULL DEFAULT 'valid' CHECK (status IN ('valid', 'void')),
    voided_at    timestamptz,
    created_by   bigint        REFERENCES users (id) ON DELETE SET NULL,
    created_at   timestamptz   NOT NULL DEFAULT now(),
    CHECK (amount > 0 OR method = 'deposit_refund')
);
CREATE INDEX payments_landlord_idx ON payments (landlord_id, paid_on DESC, id DESC);
CREATE INDEX payments_bill_idx ON payments (bill_id);
