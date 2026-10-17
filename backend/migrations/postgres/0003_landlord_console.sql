-- P2 房东后台：成员关系与咨询跟进。

-- 一个账号只属于一个房东（user_id 唯一）；owner 可管理成员，staff 只管理房源与咨询
CREATE TABLE landlord_members (
    landlord_id  bigint      NOT NULL REFERENCES landlords (id) ON DELETE CASCADE,
    user_id      bigint      NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    role         text        NOT NULL CHECK (role IN ('owner', 'staff')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (landlord_id, user_id)
);

ALTER TABLE listing_inquiries
    ADD COLUMN note       text NOT NULL DEFAULT '',
    ADD COLUMN handled_at timestamptz;

CREATE INDEX listing_images_listing_sort_idx ON listing_images (listing_id, sort, id);
