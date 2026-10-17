# 房子 Houses

> 发现更好的房源 · 让找房更便捷
> Discover better listings · Make house hunting easier

面向租客的找房网站，同时也是房东的出租记账工具。基于开源项目 [AIGCNEWS](https://github.com/Kaixxrua/AIGCNEWS) 二次开发，以 **AGPL-3.0** 开源。

## 功能

**租客（无需注册即可浏览、咨询）**
- 长租 / 短租 / 合租分类，按区域、价格、户型、特色、入住日期筛选（按日期排除已租、已预订的时段）
- 卡片式房源列表与详情、地图找房（OpenStreetMap，免 Key）、附近房源、推荐房源、今日房源动态
- AI 一键找房：一句话 → 筛选条件 + 推荐理由；配置大模型时用大模型理解，否则规则解析；无结果时自动放宽条件
- 房源订阅：新房源上架、降价时实时推送（站内 SSE + 浏览器通知 + 可选邮件）

**房东**
- 小区（地图选点）、房源、图片、上下架、不可租日期、咨询跟进、成员（主账号 / 员工）
- 出租与收租（**只记账，不收款**）：签约一次生成全部账单、登记线下收款、减免、作废收款、抄表自动入账、退租结算（押金抵扣与退还）、租约状态每日推进

**平台**
- 开通 / 停用房东，房源审核（强制下架、设为推荐）；房东之间数据严格隔离

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 · Vite · TypeScript · Pinia · vue-i18n（中 / 英）· Leaflet · PWA |
| 后端 | FastAPI · psycopg 3 · PostgreSQL 16 · Redis 7 · APScheduler |
| 部署 | Docker Compose（postgres / redis / api / web），nginx 提供静态页面并反向代理 |

## 本地开发

```bash
# 1. 数据库与缓存
docker run -d --name houses-pg -p 25432:5432 -e POSTGRES_USER=houses -e POSTGRES_PASSWORD=houses_dev_pw -e POSTGRES_DB=houses postgres:16-alpine
docker run -d --name houses-redis -p 16379:6379 redis:7-alpine

# 2. 后端（仓库根目录执行；配置见 .env.example，复制为 .env）
python -m venv backend/.venv
PYTHONUTF8=1 backend/.venv/Scripts/pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --port 8020      # 启动时自动执行数据库迁移
backend/.venv/Scripts/python -m backend.scripts.seed_demo                     # 可选：写入成都演示房源

# 3. 前端（/api 与 /uploads 代理到 8020）
cd frontend && npm install && npm run dev                                       # http://127.0.0.1:5180
```

测试：

```bash
backend/.venv/Scripts/python -m pytest backend/tests     # 需要上面的 PostgreSQL 与 Redis；会自动重建 houses_test 库
cd frontend && npm run typecheck && npm run test:unit && npm run build
```

## 部署

```bash
cp deploy/.env.production.example deploy/.env.production   # 填写密钥、域名与 SOURCE_CODE_URL
docker compose --env-file deploy/.env.production up -d --build
```

- web 只监听 `127.0.0.1:${WEB_PORT}`，对外 HTTPS 由宿主机的 Caddy / nginx 反向代理过来。
- `ENVIRONMENT=production` 时启动会自检：缺少源码地址、弱密码、非 https 地址等会直接拒绝启动。
- 备份：`sh deploy/backup.sh`（数据库 + 房源图片，保留 14 天），建议加入 crontab。
- 部署前把 `frontend/public/robots.txt` 里的 `YOUR-DOMAIN` 换成正式域名。

## 目录

```
backend/app/
  api/            路由（公开找房、AI、订阅、房东后台、平台管理、站点地图）
  domain/         纯计算规则：检索条件、计费（BillPlanner / BillLedger）、AI 规则解析
  repositories/   数据访问（全部按 landlord_id 隔离）
  services/       订阅匹配与实时推送
backend/migrations/postgres/   编号迁移（0001–0005）
frontend/src/
  views/          页面（landlord/ 房东后台，admin/ 平台管理）
  features/       各业务的 API、类型与纯函数
docs/houses-plan.md            分阶段计划与进度记录
```

## 许可证

- 代码以 [AGPL-3.0](LICENSE) 授权。通过网络提供服务时，必须向用户提供对应源码：站点页脚的「源代码」链接指向 `SOURCE_CODE_URL`。
- 本项目基于 AIGCNEWS（Copyright 2026 Kaixxrua，AGPL-3.0）。AIGCNEWS 的名称、Logo 与插画等品牌素材不在开源授权范围内，本项目未使用；详见 [NOTICE](NOTICE)。
- 第三方字体（Bangers、ZCOOL QingKe HuangYou、Kalam 等）遵循各自的 SIL OFL 1.1 许可，许可文件位于 `frontend/public/fonts/`。
