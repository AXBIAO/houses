"""演示房源的静态数据：城市、小区、房型模板。照片 key 对应 gen_demo_photos.PHOTOS。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Estate:
    name: str
    district: str
    address: str
    lat: float
    lng: float


@dataclass(frozen=True)
class Template:
    title: str
    kind: str  # long / short / shared
    bedrooms: int
    halls: int
    area: int
    price: int  # 长租、合租为月价，短租为晚价
    tags: tuple[str, ...]
    recommended: bool
    photos: tuple[str, ...]
    # 只放在这些区的小区里（例如海景房），空表示不限
    districts: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class City:
    name: str
    landlords: tuple[str, ...]
    estates: tuple[Estate, ...]
    templates: tuple[Template, ...]
    count: int
    # True：按顺序轮换模板与小区（保持原有成都数据不变）；False：随机搭配
    rotate: bool


# 坐标为 GCJ-02（高德、腾讯地图使用的坐标系）
CHENGDU = City(
    name="成都",
    landlords=("蓉城安居（演示）", "锦江短租（演示）"),
    estates=(
        Estate("天府软件园公寓", "高新区", "天府大道中段 1366 号", 30.5434, 104.0660),
        Estate("金融城雅苑", "高新区", "交子大道 177 号", 30.5790, 104.0650),
        Estate("春熙公馆", "锦江区", "春熙路北段 18 号", 30.6570, 104.0810),
        Estate("太古里 Loft", "锦江区", "中纱帽街 8 号", 30.6540, 104.0830),
        Estate("玉林小区", "武侯区", "玉林北路 12 号", 30.6290, 104.0570),
        Estate("光华公园", "青羊区", "光华大道一段 99 号", 30.6720, 104.0130),
        Estate("宽窄巷子院落", "青羊区", "宽巷子 26 号", 30.6690, 104.0560),
        Estate("建设路花园", "成华区", "建设北路二段 6 号", 30.6760, 104.1020),
        Estate("东郊记忆公寓", "成华区", "建设南支路 4 号", 30.6700, 104.1250),
        Estate("大源国际", "高新区", "剑南大道中段 998 号", 30.5530, 104.0430),
    ),
    templates=(
        Template("地铁口精装两居 · 南北通透", "long", 2, 1, 78, 4200, ("近地铁", "拎包入住", "押一付一"), True,
                 ("living_modern", "bed_master", "kitchen_open", "bath_modern", "ext_cd_residential")),
        Template("江景一居 · 可日租", "short", 1, 1, 45, 268, ("江景", "智能门锁", "可做饭"), True,
                 ("view_river", "studio_highrise", "kitchen_galley", "bath_compact")),
        Template("合租主卧 · 独立卫浴带阳台", "shared", 4, 1, 22, 1650, ("独卫", "女生合租", "月付"), False,
                 ("bed_shared_suite", "living_shared", "bath_modern", "balcony_laundry")),
        Template("整租三居 · 学区房带车位", "long", 3, 2, 112, 5800, ("车位", "学区", "电梯房"), True,
                 ("living_luxe", "bed_master", "bed_wood", "kitchen_open", "ext_cd_residential")),
        Template("Loft 复式 · 周末短租", "short", 1, 0, 52, 399, ("Loft", "投影", "近商圈"), False,
                 ("loft_stairs", "loft_bed", "kitchen_galley", "bath_compact")),
        Template("合租次卧 · 近地铁", "shared", 3, 1, 14, 980, ("近地铁", "月付", "安静"), True,
                 ("bed_shared_small", "living_shared", "kitchen_galley", "bath_compact")),
        Template("一居室 · 落地窗高层", "long", 1, 1, 56, 3600, ("落地窗", "新房", "近地铁"), False,
                 ("studio_highrise", "view_city_night", "kitchen_galley", "bath_modern")),
        Template("院落民宿 · 家庭短住", "short", 2, 1, 80, 520, ("院落", "亲子", "可停车"), True,
                 ("courtyard", "minsu_family", "living_wood", "bath_modern")),
        Template("开间公寓 · 押一付一", "long", 1, 0, 35, 2100, ("押一付一", "电梯房", "拎包入住"), False,
                 ("studio_open", "kitchen_galley", "bath_compact")),
        Template("合租大主卧 · 带飘窗", "shared", 3, 1, 18, 1380, ("飘窗", "月付", "近地铁"), False,
                 ("bed_bay", "living_shared", "kitchen_open", "bath_compact")),
        Template("精装两居 · 可养宠物", "long", 2, 1, 82, 4600, ("可养宠物", "电梯房", "拎包入住"), False,
                 ("pet_living", "bed_wood", "kitchen_open", "bath_modern", "balcony_laundry")),
        Template("商务短租 · 近会展", "short", 1, 1, 48, 318, ("近地铁", "可开发票", "智能门锁"), False,
                 ("serviced_apart", "living_compact", "bath_modern")),
    ),
    count=30,
    rotate=True,
)

SHENZHEN = City(
    name="深圳",
    landlords=("鹏城安居（演示）", "南山湾区公寓（演示）"),
    estates=(
        Estate("科技园人才公寓", "南山区", "高新南九道 21 号", 22.5280, 113.9530),
        Estate("海岸城公馆", "南山区", "文心五路 33 号", 22.5170, 113.9370),
        Estate("蛇口望海花园", "南山区", "望海路 1088 号", 22.4840, 113.9140),
        Estate("西丽留仙居", "南山区", "留仙大道 3370 号", 22.5860, 113.9560),
        Estate("车公庙丰盛雅苑", "福田区", "深南大道 6011 号", 22.5370, 114.0230),
        Estate("会展中心商务公寓", "福田区", "福华三路 88 号", 22.5330, 114.0590),
        Estate("香蜜湖景苑", "福田区", "香梅路 1062 号", 22.5470, 114.0300),
        Estate("华强北都市公寓", "福田区", "华发北路 40 号", 22.5480, 114.0890),
        Estate("东门老街公寓", "罗湖区", "解放路 2001 号", 22.5470, 114.1210),
        Estate("笋岗万象公馆", "罗湖区", "宝安北路 3008 号", 22.5640, 114.1050),
        Estate("宝安中心海景苑", "宝安区", "海秀路 23 号", 22.5560, 113.8900),
        Estate("西乡城中村长租公寓", "宝安区", "西乡大道 286 号", 22.5790, 113.8690),
        Estate("深圳北站雅园", "龙华区", "民治大道 1079 号", 22.6120, 114.0290),
        Estate("大浪人才公寓", "龙华区", "华荣路 396 号", 22.6550, 114.0150),
        Estate("坂田科技城公寓", "龙岗区", "坂雪岗大道 4012 号", 22.6440, 114.0640),
        Estate("大运新城花园", "龙岗区", "龙飞大道 666 号", 22.6990, 114.2220),
    ),
    templates=(
        Template("整租两居 · 近地铁南北通透", "long", 2, 1, 76, 7800, ("近地铁", "拎包入住", "电梯房"), True,
                 ("living_modern", "bed_master", "kitchen_open", "bath_modern", "ext_sz_towers")),
        Template("深圳湾海景三居 · 带车位", "long", 3, 2, 118, 16800, ("海景", "车位", "学区"), True,
                 ("view_sz_bay", "living_luxe", "bed_master", "kitchen_open", "ext_sz_garden"),
                 ("南山区", "宝安区")),
        Template("城中村单间 · 押一付一", "long", 1, 0, 25, 1900, ("押一付一", "近地铁", "月付"), False,
                 ("ext_sz_village", "studio_open", "bath_compact"), ("宝安区", "龙华区", "龙岗区", "罗湖区")),
        Template("合租主卧 · 独立卫浴", "shared", 4, 1, 20, 3200, ("独卫", "近地铁", "月付"), True,
                 ("bed_shared_suite", "living_shared", "bath_modern", "balcony_laundry")),
        Template("合租次卧 · 地铁口", "shared", 3, 1, 12, 2100, ("近地铁", "月付", "安静"), False,
                 ("bed_shared_small", "living_shared", "kitchen_galley", "bath_compact")),
        Template("高层一居 · 落地窗看城景", "long", 1, 1, 50, 5600, ("落地窗", "新房", "近地铁"), True,
                 ("studio_highrise", "view_city_night", "kitchen_galley", "bath_modern")),
        Template("精装开间 · 人才公寓", "long", 1, 0, 32, 3300, ("新房", "押一付一", "拎包入住"), False,
                 ("studio_open", "kitchen_galley", "bath_compact", "ext_sz_towers")),
        Template("商务短租 · 近会展地铁", "short", 1, 1, 45, 388, ("近地铁", "可开发票", "智能门锁"), False,
                 ("serviced_apart", "living_compact", "bath_modern"), ("福田区", "南山区", "罗湖区")),
        Template("Loft 复式 · 周末短租", "short", 1, 0, 50, 458, ("Loft", "投影", "近商圈"), False,
                 ("loft_stairs", "loft_bed", "kitchen_galley", "bath_compact")),
        Template("精装两居 · 可养宠物", "long", 2, 1, 80, 8200, ("可养宠物", "电梯房", "拎包入住"), False,
                 ("pet_living", "bed_wood", "kitchen_open", "bath_modern", "balcony_laundry")),
        Template("一居室 · 带飘窗近口岸", "long", 1, 1, 48, 4800, ("飘窗", "近地铁", "押一付一"), False,
                 ("bed_bay", "living_compact", "kitchen_galley", "bath_compact"), ("罗湖区", "福田区")),
        Template("海景民宿 · 家庭短住", "short", 2, 1, 78, 628, ("海景", "亲子", "可做饭"), True,
                 ("view_sz_bay", "minsu_family", "living_cream", "bath_modern"), ("南山区", "宝安区")),
        Template("奶油风两居 · 小区园林", "long", 2, 1, 72, 6900, ("新房", "电梯房", "可养宠物"), False,
                 ("living_cream", "bed_wood", "kitchen_open", "bath_modern", "ext_sz_garden")),
    ),
    count=36,
    rotate=False,
)

CITIES: tuple[City, ...] = (CHENGDU, SHENZHEN)
