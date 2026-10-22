"""写入演示房源（成都、深圳），可重复执行：先清掉演示房东的数据再重建。

照片来自 data/demo-photos（由 gen_demo_photos 生成，可用 --photos 或 DEMO_PHOTO_DIR 指定）；
目录不存在或缺图时只是不挂照片，不影响数据导入。

usage (项目根目录): backend/.venv/Scripts/python -m backend.scripts.seed_demo [--photos DIR]
"""
from __future__ import annotations

import argparse
import os
import random
from datetime import date, timedelta
from pathlib import Path

from backend.app.core.media import remove_public_file, save_listing_image
from backend.app.core.postgres_database import postgres_database
from backend.app.core.postgres_migrations import PostgresMigrationRunner
from backend.scripts.demo_data import CITIES, City, Estate, Template

DEMO_LANDLORDS = tuple(name for city in CITIES for name in city.landlords)
DEFAULT_PHOTO_DIR = Path(__file__).resolve().parents[2] / "data" / "demo-photos"
MAX_PHOTOS = 4
# 每个城市只有前若干套可能被标为推荐，避免首页推荐全是同一城市
RECOMMENDED_LIMIT = 24

# 按外键依赖顺序清空演示房东名下的业务数据（房东本身与成员账号保留，账号重跑后照常可用）
RESET_STATEMENTS = (
    "DELETE FROM payments WHERE landlord_id = ANY(%s)",
    "DELETE FROM bill_items WHERE bill_id IN (SELECT id FROM bills WHERE landlord_id = ANY(%s))",
    "DELETE FROM meter_readings WHERE landlord_id = ANY(%s)",
    "DELETE FROM bills WHERE landlord_id = ANY(%s)",
    "DELETE FROM leases WHERE landlord_id = ANY(%s)",
    "DELETE FROM renters WHERE landlord_id = ANY(%s)",
    "DELETE FROM fee_items WHERE landlord_id = ANY(%s)",
    "DELETE FROM listing_inquiries WHERE landlord_id = ANY(%s)",
    "DELETE FROM listings WHERE landlord_id = ANY(%s)",
    "DELETE FROM estates WHERE landlord_id = ANY(%s)",
)


def _landlords(conn, names: tuple[str, ...], phone_offset: int) -> list[int]:
    """按名称查找或创建演示房东。不删除房东行，避免级联删掉已绑定的成员账号。"""
    ids = []
    for i, name in enumerate(names):
        row = conn.execute("SELECT id FROM landlords WHERE name = %s ORDER BY id LIMIT 1", (name,)).fetchone()
        if row is None:
            row = conn.execute("INSERT INTO landlords (name, contact_name, contact_phone) VALUES (%s, %s, %s) RETURNING id",
                               (name, "管家", f"1380000{phone_offset + i:04d}")).fetchone()
        ids.append(row["id"])
    return ids


def _reset(conn, ids: list[int]) -> list[str]:
    """返回被删房源的图片地址，提交后再删文件。"""
    urls = [r["url"] for r in conn.execute(
        "SELECT i.url FROM listing_images i JOIN listings l ON l.id = i.listing_id WHERE l.landlord_id = ANY(%s)", (ids,),
    ).fetchall()]
    for statement in RESET_STATEMENTS:
        conn.execute(statement, (ids,))
    return urls


def _pairs(city: City, rng: random.Random) -> list[tuple[Template, int]]:
    """为每套房源选（模板, 小区下标）。成都按顺序轮换，深圳随机搭配且遵守模板的区域限制。"""
    if city.rotate:
        return [(city.templates[i % len(city.templates)], i % len(city.estates)) for i in range(city.count)]
    pairs = []
    for _ in range(city.count):
        template = rng.choice(city.templates)
        allowed = [i for i, e in enumerate(city.estates) if not template.districts or e.district in template.districts]
        pairs.append((template, rng.choice(allowed)))
    return pairs


def _pick_photos(template: Template, photo_dir: Path | None, rng: random.Random) -> list[bytes]:
    """封面固定用模板第一张，其余打乱后取若干张，让同类房源的图不完全一样。"""
    if photo_dir is None:
        return []
    rest = list(template.photos[1:])
    rng.shuffle(rest)
    keys = [template.photos[0], *rest][: rng.randint(MAX_PHOTOS - 1, MAX_PHOTOS)]
    files = [photo_dir / f"{key}.webp" for key in keys]
    return [f.read_bytes() for f in files if f.is_file()]


def _insert_listing(conn, rng: random.Random, today: date, landlord_id: int, estate_id: int, estate: Estate,
                    template: Template, index: int) -> int:
    t = template
    jitter = max(1, t.price // 40)  # 价格浮动约 ±5%，并取整到 10 / 100 元
    step = 10 if t.kind == "short" else 100
    price = round((t.price + rng.randint(-2, 2) * jitter) / step) * step
    total_floors = rng.choice([8, 18, 26, 32, 33]) if t.kind != "short" else 32
    return conn.execute(
        "INSERT INTO listings (landlord_id, estate_id, building, unit_no, rent_type, title, description, bedrooms, halls, "
        "baths, area, floor, total_floors, orientation, price_month, price_night, deposit_months, min_months, min_nights, "
        "tags, status, recommended, available_from, published_at) VALUES "
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'published', %s, %s, "
        "now() - make_interval(hours => %s)) RETURNING id",
        (
            landlord_id, estate_id, f"{rng.randint(1, 9)} 栋", f"{rng.randint(1, 30)}0{rng.randint(1, 6)}",
            t.kind, f"{estate.name} · {t.title}",
            f"{estate.name}{t.title}，位于{estate.district}{estate.address}。小区配套成熟，周边生活便利，看房请提前预约。",
            t.bedrooms, t.halls, t.area + rng.randint(-5, 8), rng.randint(2, total_floors - 1), total_floors,
            rng.choice(["南", "南北", "东南", "西"]),
            None if t.kind == "short" else price,
            price if t.kind == "short" else None,
            0 if t.kind == "short" else 1, 1 if t.kind != "long" else rng.choice([1, 3, 6]), 1 if t.kind == "short" else 30,
            list(t.tags), t.recommended and index < RECOMMENDED_LIMIT,
            today if index % 5 else today + timedelta(days=20),
            index * 3 + rng.randint(0, 2),
        ),
    ).fetchone()["id"]


def _attach_photos(conn, listing_id: int, photos: list[bytes]) -> None:
    urls = [save_listing_image(listing_id, data) for data in photos]
    for sort, url in enumerate(urls):
        conn.execute("INSERT INTO listing_images (listing_id, url, sort) VALUES (%s, %s, %s)", (listing_id, url, sort))
    if urls:
        conn.execute("UPDATE listings SET cover_url = %s WHERE id = %s", (urls[0], listing_id))


def _seed_city(conn, city: City, rng: random.Random, today: date, photo_dir: Path | None, phone_offset: int) -> int:
    landlord_ids = _landlords(conn, city.landlords, phone_offset)
    estate_ids = [
        conn.execute(
            "INSERT INTO estates (landlord_id, name, city, district, address, lat, lng) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (landlord_ids[i % len(landlord_ids)], e.name, city.name, e.district, e.address, e.lat, e.lng),
        ).fetchone()["id"]
        for i, e in enumerate(city.estates)
    ]
    for index, (template, estate_index) in enumerate(_pairs(city, rng)):
        landlord_id = landlord_ids[estate_index % len(landlord_ids)]
        listing_id = _insert_listing(conn, rng, today, landlord_id, estate_ids[estate_index], city.estates[estate_index],
                                     template, index)
        _attach_photos(conn, listing_id, _pick_photos(template, photo_dir, rng))
        if template.kind == "short" and index < len(city.templates):
            start = today + timedelta(days=rng.randint(1, 6))
            conn.execute("INSERT INTO listing_unavailability (listing_id, start_date, end_date, kind) VALUES (%s, %s, %s, 'booking')",
                         (listing_id, start, start + timedelta(days=3)))
    return city.count


def seed(rng_seed: int = 7, photo_dir: Path | None = None) -> int:
    rng = random.Random(rng_seed)
    today = date.today()
    with postgres_database.transaction() as conn:
        all_ids = [r["id"] for r in conn.execute("SELECT id FROM landlords WHERE name = ANY(%s)", (list(DEMO_LANDLORDS),)).fetchall()]
        removed_images = _reset(conn, all_ids)
        total, offset = 0, 0
        for city in CITIES:
            total += _seed_city(conn, city, rng, today, photo_dir, offset)
            offset += len(city.landlords)
    for url in removed_images:
        remove_public_file(url)
    return total


def _photo_dir(cli_value: str | None) -> Path | None:
    raw = cli_value or os.environ.get("DEMO_PHOTO_DIR")
    path = Path(raw) if raw else DEFAULT_PHOTO_DIR
    return path if path.is_dir() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="重建演示房源")
    parser.add_argument("--photos", help="演示照片目录，默认 data/demo-photos")
    photo_dir = _photo_dir(parser.parse_args().photos)
    postgres_database.open()
    try:
        PostgresMigrationRunner(postgres_database).apply()
        count = seed(photo_dir=photo_dir)
        print(f"seeded {count} demo listings" + (f" with photos from {photo_dir}" if photo_dir else " (no photos)"))
    finally:
        postgres_database.close()


if __name__ == "__main__":
    main()
