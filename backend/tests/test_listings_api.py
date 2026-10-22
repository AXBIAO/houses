"""公开找房接口集成测试。本模块自建一组房源，ID 通过 world fixture 传递。"""
from __future__ import annotations

import os
from datetime import date, timedelta

import psycopg
import pytest
import redis
from psycopg.rows import dict_row

TODAY = date.today()


def _iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _conninfo() -> str:
    return (f"host={os.environ['POSTGRES_HOST']} port={os.environ['POSTGRES_PORT']} user=houses "
            f"password={os.environ['POSTGRES_PASSWORD']} dbname=houses_test")


@pytest.fixture(scope="module")
def world(client):
    """L1 长租推荐 / L2 短租有预订 / L3 合租 30 天后可租 / L4 草稿 / L5 房东已停用。"""
    with psycopg.connect(_conninfo(), autocommit=True, row_factory=dict_row) as conn:
        def one(sql, params):
            return conn.execute(sql, params).fetchone()["id"]

        active = one("INSERT INTO landlords (name) VALUES ('测试房东甲') RETURNING id", ())
        disabled = one("INSERT INTO landlords (name, status) VALUES ('停用房东', 'disabled') RETURNING id", ())
        est = {}
        for key, landlord, district, lat, lng in [
            ("gx", active, "高新区", 30.5434, 104.0660),
            ("jj", active, "锦江区", 30.6570, 104.0810),
            ("wh", active, "武侯区", 30.6290, 104.0570),
            ("off", disabled, "成华区", 30.6760, 104.1020),
        ]:
            est[key] = one("INSERT INTO estates (landlord_id, name, city, district, address, lat, lng) "
                           "VALUES (%s, %s, '成都', %s, '测试路 1 号', %s, %s) RETURNING id",
                           (landlord, f"{district}小区", district, lat, lng))

        def listing(landlord, estate, rent_type, title, *, month=None, night=None, bedrooms=1, tags=(),
                    status="published", hours_ago=1, recommended=False, available_days=None, min_months=1, min_nights=1):
            return one(
                "INSERT INTO listings (landlord_id, estate_id, rent_type, title, bedrooms, area, price_month, price_night, "
                "tags, status, recommended, available_from, min_months, min_nights, published_at) "
                "VALUES (%s, %s, %s, %s, %s, 50, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CASE WHEN %s = 'published' THEN now() - make_interval(hours => %s) END) RETURNING id",
                (landlord, estate, rent_type, title, bedrooms, month, night, list(tags), status, recommended,
                 None if available_days is None else TODAY + timedelta(days=available_days), min_months, min_nights,
                 status, hours_ago),
            )

        ids = {
            "L1": listing(active, est["gx"], "long", "地铁口两居", month=3000, bedrooms=2, tags=("近地铁", "押一付一"),
                          recommended=True, min_months=3),
            "L2": listing(active, est["jj"], "short", "江景一居", night=300, tags=("江景",), hours_ago=30, min_nights=2),
            "L3": listing(active, est["wh"], "shared", "合租主卧", month=1200, bedrooms=4, tags=("独卫", "近地铁"),
                          hours_ago=40, available_days=30),
            "L4": listing(active, est["gx"], "long", "草稿房源", month=2000, status="draft"),
            "L5": listing(disabled, est["off"], "long", "停用房东的房", month=2500),
        }
        conn.execute("INSERT INTO listing_unavailability (listing_id, start_date, end_date, kind) VALUES (%s, %s, %s, 'booking')",
                     (ids["L2"], TODAY + timedelta(days=5), TODAY + timedelta(days=8)))
        conn.execute("INSERT INTO listing_images (listing_id, url, sort) VALUES (%s, '/img/a.jpg', 1), (%s, '/img/b.jpg', 0)",
                     (ids["L1"], ids["L1"]))
    return ids


@pytest.fixture()
def no_throttle():
    r = redis.Redis(host="localhost", port=int(os.environ["REDIS_PORT"]), db=15)
    for key in r.scan_iter("houses:inquiry-*"):
        r.delete(key)


def _ids(client, **params):
    res = client.get("/api/listings", params=params)
    assert res.status_code == 200, res.text
    return [item["id"] for item in res.json()["items"]]


def _names(world, *keys):
    return [world[k] for k in keys]


def test_list_shows_only_public(client, world):
    res = client.get("/api/listings").json()
    assert sorted(i["id"] for i in res["items"]) == sorted(_names(world, "L1", "L2", "L3"))
    assert res["total"] == 3
    assert _ids(client) == _names(world, "L1", "L2", "L3")  # 最新上架在前


def test_filter_by_type_price_bedrooms(client, world):
    assert _ids(client, type="short") == _names(world, "L2")
    assert _ids(client, type="long", minPrice=2500) == _names(world, "L1")
    assert sorted(_ids(client, maxPrice=1500)) == sorted(_names(world, "L2", "L3"))
    assert _ids(client, bedrooms=3) == _names(world, "L3")
    assert _ids(client, sort="price_asc") == _names(world, "L2", "L3", "L1")


def test_filter_by_tags_and_keyword(client, world):
    assert sorted(_ids(client, tags="近地铁")) == sorted(_names(world, "L1", "L3"))
    assert _ids(client, tags="近地铁,押一付一") == _names(world, "L1")
    assert _ids(client, q="江景") == _names(world, "L2")
    assert _ids(client, q="锦江") == _names(world, "L2")
    assert _ids(client, q="100%_") == []


def test_short_stay_availability(client, world):
    assert world["L2"] not in _ids(client, type="short", moveIn=_iso(6), moveOut=_iso(8))
    assert world["L2"] not in _ids(client, type="short", moveIn=_iso(3), moveOut=_iso(6))
    assert world["L2"] in _ids(client, type="short", moveIn=_iso(8), moveOut=_iso(10))
    assert world["L2"] in _ids(client, type="short", moveIn=_iso(1), moveOut=_iso(5))
    # 少于最短入住晚数
    assert world["L2"] not in _ids(client, type="short", moveIn=_iso(10), moveOut=_iso(11))


def test_long_stay_months_and_available_from(client, world):
    assert world["L1"] not in _ids(client, months=1)
    assert world["L1"] in _ids(client, months=3)
    assert world["L3"] not in _ids(client, type="shared", moveIn=_iso(0), months=6)
    assert world["L3"] in _ids(client, type="shared", moveIn=_iso(30), months=6)


@pytest.mark.parametrize(
    "params",
    [
        {"moveIn": "2000-01-01"},
        {"moveIn": _iso(5), "moveOut": _iso(5)},
        {"minPrice": 5000, "maxPrice": 100},
        {"lat": 30.5},
        {"tags": ",".join(f"t{i}" for i in range(9))},
    ],
)
def test_invalid_filters_rejected(client, world, params):
    assert client.get("/api/listings", params=params).status_code == 422


def test_nearby_sorted_by_distance(client, world):
    res = client.get("/api/listings", params={"lat": 30.544, "lng": 104.066, "radiusKm": 20, "sort": "distance"}).json()
    ids = [i["id"] for i in res["items"]]
    assert ids[0] == world["L1"]
    assert set(ids) == set(_names(world, "L1", "L2", "L3"))
    distances = [i["distanceKm"] for i in res["items"]]
    assert distances == sorted(distances) and distances[0] < 0.5
    assert _ids(client, lat=30.544, lng=104.066, radiusKm=1) == _names(world, "L1")


def test_map_bbox(client, world):
    res = client.get("/api/listings/map", params={"bbox": "104.07,30.65,104.09,30.66"})
    assert res.status_code == 200
    assert [i["id"] for i in res.json()["items"]] == _names(world, "L2")
    assert client.get("/api/listings/map").status_code == 422
    assert client.get("/api/listings/map", params={"bbox": "1,2,3"}).status_code == 422
    assert client.get("/api/listings/map", params={"bbox": "105,30,104,31"}).status_code == 422


def test_home_feed(client, world):
    res = client.get("/api/listings/home").json()
    today = {i["id"]: i["isToday"] for i in res["today"]}
    assert today[world["L1"]] is True and today[world["L2"]] is False
    assert [i["id"] for i in res["recommended"]] == _names(world, "L1")
    assert res["todayCount"] == 1


def test_facets(client, world):
    res = client.get("/api/listings/facets").json()
    districts = {d["value"]: d["count"] for d in res["districts"]}
    assert districts == {"高新区": 1, "锦江区": 1, "武侯区": 1}
    assert {"value": "近地铁", "count": 2} in res["tags"]
    assert [(c["value"], c["count"]) for c in res["cities"]] == [("成都", 3)]
    assert isinstance(res["cities"][0]["lat"], float) and isinstance(res["cities"][0]["lng"], float)


def test_detail(client, world):
    res = client.get(f"/api/listings/{world['L2']}")
    assert res.status_code == 200
    body = res.json()
    assert body["rentType"] == "short" and body["price"] == 300
    assert body["unavailable"] == [{"start": _iso(5), "end": _iso(8)}]
    assert body["landlordName"] == "测试**"
    assert client.get(f"/api/listings/{world['L1']}").json()["images"] == ["/img/b.jpg", "/img/a.jpg"]


@pytest.mark.parametrize("key", ["L4", "L5"])
def test_detail_hidden(client, world, key):
    assert client.get(f"/api/listings/{world[key]}").status_code == 404


def test_inquiry_created_and_deduplicated(client, world, sql, no_throttle):
    body = {"name": "王先生", "phone": "13900000001", "message": "周末能看房吗", "moveIn": _iso(8), "moveOut": _iso(10)}
    res = client.post(f"/api/listings/{world['L2']}/inquiries", json=body)
    assert res.status_code == 201, res.text
    rows = sql("SELECT listing_id, name, phone, status, user_id FROM listing_inquiries WHERE id = %s", (res.json()["id"],))
    assert rows == [(world["L2"], "王先生", "13900000001", "new", None)]
    assert client.post(f"/api/listings/{world['L2']}/inquiries", json=body).status_code == 429


def test_inquiry_validation(client, world, no_throttle):
    url = f"/api/listings/{world['L1']}/inquiries"
    assert client.post(url, json={"name": "李", "phone": "123"}).status_code == 422
    assert client.post(url, json={"name": "  ", "phone": "13900000002"}).status_code == 422
    assert client.post(url, json={"name": "李", "phone": "13900000002", "moveIn": _iso(5), "moveOut": _iso(3)}).status_code == 422
    assert client.post(f"/api/listings/{world['L4']}/inquiries", json={"name": "李", "phone": "13900000002"}).status_code == 404


def test_inquiry_ip_rate_limit(client, world, no_throttle):
    url = f"/api/listings/{world['L1']}/inquiries"
    codes = [client.post(url, json={"name": "赵", "phone": f"1390000010{i}"}).status_code for i in range(6)]
    assert codes == [201] * 5 + [429]
