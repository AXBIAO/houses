"""用 OpenAI 兼容的生图接口生成演示房源照片（中介实拍风），供 seed_demo 挂到演示房源上。

产物写入 data/demo-photos/<key>.webp（3:2，长边 1600），目录已被 .gitignore 忽略。
已存在的文件默认跳过，--force 重新生成。

环境变量：IMAGE_API_BASE（如 https://api.openai.com/v1）、IMAGE_API_KEY、IMAGE_MODEL（默认 gpt-image-1）
usage (项目根目录): backend/.venv/Scripts/python -m backend.scripts.gen_demo_photos [--keys a,b] [--force]
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data" / "demo-photos"
MAX_SIDE = 1600
WORKERS = 4
ATTEMPTS = 3
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

STYLE = (
    "真实的中国租房平台房源实拍照片，房产经纪人用手机广角镜头平拍，相机高度约 1.4 米，"
    "白天自然光从窗户照入，曝光略偏亮，色彩真实不过度调色，墙角与家具有正常的使用痕迹，"
    "物品摆放整洁但不像样板间，画面纵向线条垂直，照片质感（轻微噪点、真实阴影），"
    "不要出现任何人、动物、文字、Logo、水印、边框，不要 3D 渲染感，不要插画风"
)

# key -> 画面描述。key 被 seed_demo 引用，改名时两边一起改。
PHOTOS: dict[str, str] = {
    "living_modern": "现代简约风两居室客厅，浅灰布艺沙发、白色电视柜和挂壁电视，浅色木地板，一侧推拉门通往阳台，窗外是对面的高层住宅",
    "living_wood": "原木风客厅，橡木色地板与木质茶几，米白色沙发，绿植，窗帘半拉，墙上挂一幅简单装饰画",
    "living_cream": "奶油风客厅，奶白色弧形沙发，圆角茶几，暖白色墙面，落地灯，窗外阳光洒在地板上",
    "living_compact": "小户型一室一厅的客厅兼餐厅，双人小沙发、可折叠餐桌和两把椅子，靠墙书架，空间紧凑但整洁",
    "living_shared": "合租房的公共客厅，长沙发、餐桌和四把椅子，开放式鞋柜，墙上贴有简单的值日表（不可读），干净明亮",
    "living_luxe": "三居室大客厅，深灰色真皮沙发，大理石纹理茶几，L 形落地窗，窗外是城市高楼天际线，层高感明显",
    "bed_master": "主卧室，1.8 米双人床铺着浅灰色床品，两侧床头柜和台灯，整面衣柜，大窗户带纱帘",
    "bed_wood": "原木风卧室，1.5 米木质床架，白色床品，床头一盏小吊灯，木质书桌靠窗，窗外有树",
    "bed_bay": "带飘窗的卧室，飘窗上放着坐垫和小靠枕，1.5 米床，白色衣柜，阳光从飘窗照进来",
    "bed_shared_small": "合租次卧，1.2 米单人床，白色小衣柜，靠墙书桌和椅子，房间约 12 平米，窗户朝向小区内部",
    "bed_shared_suite": "合租主卧带独立卫生间，1.5 米床，门口可见卫生间的玻璃门，靠窗有一张书桌，另一侧是小阳台推拉门",
    "studio_open": "开间公寓全景，一侧是 1.5 米床，另一侧是小沙发和书桌，入户处有一字型小厨房，地面浅色瓷砖",
    "studio_highrise": "高层一居室，整面落地窗，窗外是城市高楼与远处的天空，室内是双人床和单人沙发，简洁现代",
    "loft_stairs": "Loft 复式公寓，挑高约 4.5 米，下层客厅有沙发和投影幕布，一侧是钢木楼梯通往上层卧室，上层有玻璃栏杆",
    "loft_bed": "Loft 公寓上层卧室，斜坡屋顶下的双人床，玻璃栏杆外可以看到楼下的客厅，暖色床头灯",
    "kitchen_open": "开放式厨房，L 形白色橱柜，石英石台面，燃气灶与油烟机，冰箱和微波炉，台面上有少量厨具",
    "kitchen_galley": "一字型小厨房，浅灰色橱柜，嵌入式电磁炉，水槽上方有窗，墙面白色瓷砖",
    "bath_modern": "干湿分离的卫生间，玻璃淋浴房，悬挂式洗手台和镜柜，灰色仿石瓷砖，马桶，毛巾架",
    "bath_compact": "小户型卫生间，淋浴帘隔开淋浴区，白色洗手盆和镜子，墙上挂着热水器，干净的白色瓷砖",
    "balcony_laundry": "生活阳台，滚筒洗衣机和晾衣杆，几盆绿植，窗外是对面的居民楼，阳光充足",
    "view_river": "从高层公寓客厅望出去的江景，宽阔的江面和对岸的城市楼群，近景是窗框和一把单人椅",
    "view_sz_bay": "从深圳南山高层住宅阳台望出去的深圳湾海景，海面、跨海大桥和远处的山，近景是阳台栏杆和一张小圆桌",
    "view_city_night": "傍晚时分从公寓落地窗看出去的城市夜景，高楼灯光亮起，室内开着暖色落地灯，窗边一张单人沙发",
    "courtyard": "成都老城区的川西小院民宿，青砖灰瓦，天井里有竹子和石桌石凳，木格窗，院门半开",
    "minsu_family": "民宿家庭房，一张 1.8 米大床和一张 1.2 米小床，木质家具，竹编灯罩，墙面白色，窗外是院子",
    "serviced_apart": "商务酒店式公寓房间，双人床、书桌和办公椅，墙上有电视，入户处有小冰箱和胶囊咖啡机，酒店风格床品",
    "pet_living": "可养宠物的两居室客厅，耐磨地板，布艺沙发上铺着防护垫，角落有猫爬架和宠物窝（画面中没有动物）",
    "ext_sz_towers": "深圳南山的高层住宅小区外观，三十多层的住宅楼，小区大门有门岗，人行道上有行道树，晴天蓝天，街拍视角",
    "ext_sz_village": "深圳城中村改造的长租公寓楼外观，八九层的楼房外立面刷新过，一楼是便利店和快递柜，巷子干净，抬头可见楼间一线天",
    "ext_sz_garden": "深圳小区内部园林，棕榈树和草坪，儿童游乐区和环形步道，背景是高层住宅楼，阳光明亮",
    "ext_cd_residential": "成都的电梯住宅小区外观，二三十层的住宅楼，小区入口的绿化带和银杏树，阴天柔和光线",
}


def _request_image(prompt: str, base: str, key: str, model: str) -> bytes:
    body = json.dumps({"model": model, "prompt": prompt, "size": "1536x1024", "n": 1}).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/images/generations", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            result = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"HTTP {err.code}: {err.read().decode('utf-8', 'replace')[:300]}") from err
    item = (result.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urllib.request.urlopen(urllib.request.Request(item["url"], headers={"User-Agent": BROWSER_UA}), timeout=120) as res:
            return res.read()
    raise RuntimeError(f"生图返回异常：{json.dumps(result, ensure_ascii=False)[:300]}")


def generate(key: str, base: str, api_key: str, model: str) -> str:
    prompt = f"{PHOTOS[key]}。{STYLE}"
    last_err: Exception | None = None
    for _ in range(ATTEMPTS):
        try:
            raw = _request_image(prompt, base, api_key, model)
            break
        except Exception as exc:  # noqa: BLE001 - 上游偶发失败，重试
            last_err = exc
    else:
        raise RuntimeError(f"{key} 重试 {ATTEMPTS} 次仍失败：{last_err}")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = OUT_DIR / f"{key}.webp"
    img.save(out, "WEBP", quality=82, method=6)
    return f"{key}: {img.width}x{img.height} {out.stat().st_size // 1024}KB"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成演示房源照片")
    parser.add_argument("--keys", default="", help="逗号分隔，默认全部")
    parser.add_argument("--force", action="store_true", help="覆盖已有文件")
    args = parser.parse_args()
    base, api_key = os.environ.get("IMAGE_API_BASE", ""), os.environ.get("IMAGE_API_KEY", "")
    if not base or not api_key:
        print("缺少 IMAGE_API_BASE / IMAGE_API_KEY 环境变量", file=sys.stderr)
        return 1
    model = os.environ.get("IMAGE_MODEL", "gpt-image-1")
    wanted = [k for k in args.keys.split(",") if k] or list(PHOTOS)
    unknown = [k for k in wanted if k not in PHOTOS]
    if unknown:
        print(f"未知的 key：{', '.join(unknown)}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = [k for k in wanted if args.force or not (OUT_DIR / f"{k}.webp").exists()]
    failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(generate, k, base, api_key, model): k for k in todo}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"失败 {futures[future]}: {exc}", file=sys.stderr, flush=True)
    print(f"完成 {len(todo) - failed}/{len(todo)}，跳过 {len(wanted) - len(todo)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
