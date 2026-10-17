"""写入开发用演示房源（成都），可重复执行：先清掉演示房东的数据再重建。

usage (项目根目录): backend/.venv/Scripts/python -m backend.scripts.seed_demo
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from backend.app.core.postgres_database import postgres_database
from backend.app.core.postgres_migrations import PostgresMigrationRunner

DEMO_LANDLORDS = ("蓉城安居（演示）", "锦江短租（演示）")

# (小区, 区, 地址, 纬度, 经度)
ESTATES = [
    ("天府软件园公寓", "高新区", "天府大道中段 1366 号", 30.5434, 104.0660),
    ("金融城雅苑", "高新区", "交子大道 177 号", 30.5790, 104.0650),
    ("春熙公馆", "锦江区", "春熙路北段 18 号", 30.6570, 104.0810),
    ("太古里 Loft", "锦江区", "中纱帽街 8 号", 30.6540, 104.0830),
    ("玉林小区", "武侯区", "玉林北路 12 号", 30.6290, 104.0570),
    ("光华公园", "青羊区", "光华大道一段 99 号", 30.6720, 104.0130),
    ("宽窄巷子院落", "青羊区", "宽巷子 26 号", 30.6690, 104.0560),
    ("建设路花园", "成华区", "建设北路二段 6 号", 30.6760, 104.1020),
    ("东郊记忆公寓", "成华区", "建设南支路 4 号", 30.6700, 104.1250),
    ("大源国际", "高新区", "剑南大道中段 998 号", 30.5530, 104.0430),
]

# (标题, 类型, 室, 厅, 面积, 月价/晚价, 标签, 推荐)
TEMPLATES = [
    ("地铁口精装两居 · 南北通透", "long", 2, 1, 78, 4200, ["近地铁", "拎包入住", "押一付一"], True),
    ("江景一居 · 可日租", "short", 1, 1, 45, 268, ["江景", "智能门锁", "可做饭"], True),
    ("合租主卧 · 独立卫浴带阳台", "shared", 4, 1, 22, 1650, ["独卫", "女生合租", "月付"], False),
    ("整租三居 · 学区房带车位", "long", 3, 2, 112, 5800, ["车位", "学区", "电梯房"], True),
    ("Loft 复式 · 周末短租", "short", 1, 0, 52, 399, ["Loft", "投影", "近商圈"], False),
    ("合租次卧 · 近地铁", "shared", 3, 1, 14, 980, ["近地铁", "月付", "安静"], True),
    ("一居室 · 落地窗高层", "long", 1, 1, 56, 3600, ["落地窗", "新房", "近地铁"], False),
    ("院落民宿 · 家庭短住", "short", 2, 1, 80, 520, ["院落", "亲子", "可停车"], True),
    ("开间公寓 · 押一付一", "long", 1, 0, 35, 2100, ["押一付一", "电梯房", "拎包入住"], False),
    ("合租大主卧 · 带飘窗", "shared", 3, 1, 18, 1380, ["飘窗", "月付", "近地铁"], False),
    ("精装两居 · 可养宠物", "long", 2, 1, 82, 4600, ["可养宠物", "电梯房", "拎包入住"], False),
    ("商务短租 · 近会展", "short", 1, 1, 48, 318, ["近地铁", "可开发票", "智能门锁"], False),
]


def _reset(conn) -> None:
    ids = [r["id"] for r in conn.execute("SELECT id FROM landlords WHERE name = ANY(%s)", (list(DEMO_LANDLORDS),)).fetchall()]
    if not ids:
        return
    conn.execute("DELETE FROM listing_inquiries WHERE landlord_id = ANY(%s)", (ids,))
    conn.execute("DELETE FROM listings WHERE landlord_id = ANY(%s)", (ids,))
    conn.execute("DELETE FROM estates WHERE landlord_id = ANY(%s)", (ids,))
    conn.execute("DELETE FROM landlords WHERE id = ANY(%s)", (ids,))


def seed(count: int = 30, rng_seed: int = 7) -> int:
    rng = random.Random(rng_seed)
    today = date.today()
    with postgres_database.transaction() as conn:
        _reset(conn)
        landlord_ids = [
            conn.execute("INSERT INTO landlords (name, contact_name, contact_phone) VALUES (%s, %s, %s) RETURNING id",
                         (name, "管家", f"1380000{i:04d}")).fetchone()["id"]
            for i, name in enumerate(DEMO_LANDLORDS)
        ]
        estate_ids = [
            conn.execute(
                "INSERT INTO estates (landlord_id, name, city, district, address, lat, lng) "
                "VALUES (%s, %s, '成都', %s, %s, %s, %s) RETURNING id",
                (landlord_ids[i % 2], name, district, address, lat, lng),
            ).fetchone()["id"]
            for i, (name, district, address, lat, lng) in enumerate(ESTATES)
        ]
        for i in range(count):
            title, kind, bedrooms, halls, area, price, tags, recommended = TEMPLATES[i % len(TEMPLATES)]
            estate_index = i % len(ESTATES)
            estate_name = ESTATES[estate_index][0]
            listing_id = conn.execute(
                "INSERT INTO listings (landlord_id, estate_id, building, unit_no, rent_type, title, description, bedrooms, halls, "
                "baths, area, floor, total_floors, orientation, price_month, price_night, deposit_months, min_months, min_nights, "
                "tags, status, recommended, available_from, published_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, 32, %s, %s, %s, %s, %s, %s, %s, 'published', %s, %s, "
                "now() - make_interval(hours => %s)) RETURNING id",
                (
                    landlord_ids[estate_index % 2], estate_ids[estate_index], f"{rng.randint(1, 9)} 栋", f"{rng.randint(1, 30)}0{rng.randint(1, 6)}",
                    kind, f"{estate_name} · {title}",
                    f"{estate_name}{title}。小区配套成熟，周边生活便利，看房请提前预约。",
                    bedrooms, halls, area + rng.randint(-5, 8), rng.randint(2, 30), rng.choice(["南", "南北", "东南", "西"]),
                    None if kind == "short" else price + rng.randint(-3, 6) * 100,
                    price + rng.randint(-2, 4) * 10 if kind == "short" else None,
                    0 if kind == "short" else 1, 1 if kind != "long" else rng.choice([1, 3, 6]), 1 if kind == "short" else 30,
                    tags, recommended and i < len(TEMPLATES) * 2,
                    today if i % 5 else today + timedelta(days=20),
                    i * 3 + rng.randint(0, 2),
                ),
            ).fetchone()["id"]
            if kind == "short" and i < len(TEMPLATES):
                start = today + timedelta(days=rng.randint(1, 6))
                conn.execute("INSERT INTO listing_unavailability (listing_id, start_date, end_date, kind) VALUES (%s, %s, %s, 'booking')",
                             (listing_id, start, start + timedelta(days=3)))
    return count


def main() -> None:
    postgres_database.open()
    try:
        PostgresMigrationRunner(postgres_database).apply()
        print(f"seeded {seed()} demo listings")
    finally:
        postgres_database.close()


if __name__ == "__main__":
    main()
