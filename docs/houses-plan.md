# 房子 Houses · 实施计划

> 发现更好的房源 · 让找房更便捷（Discover better listings · Make house hunting easier）

## 0. 前提与约束

- **代码来源**：基于 [Kaixxrua/AIGCNEWS](https://github.com/Kaixxrua/AIGCNEWS)（AGPL-3.0）修改。本项目整体按 **AGPL-3.0** 发布：
  - 保留 `LICENSE`、`NOTICE` 中原作者版权声明；被修改的源文件头部注明「Modified for Houses」
  - 网站页脚提供「源代码」链接（AGPL §13：通过网络提供服务时须向用户提供对应源码），上线前必须把仓库公开
- **不得使用 AIGCNEWS 品牌素材**（名称、Logo、字标、favicon、漫画报头插图等，NOTICE 声明保留所有权利），全部替换为 Houses 自己的
- **取代 ruoyi-tdesign**：多房东、房源、出租、收租、平台管理员全部用本项目重写；ruoyi 版本（`C:\AYBIAO\ruoyi-tdesign`）作为业务规则参考，规则文档见其 `doc/rental-schema.md`
- 短租：按日期筛空房 + 咨询，不做在线预订和支付
- 地图：先用 OpenStreetMap（Leaflet，免 Key），后续可换高德/腾讯

## 1. 技术栈（沿用 AIGCNEWS）

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Pinia + vue-i18n（中/英），漫画主题样式、PWA、手机布局 |
| 后端 | FastAPI + psycopg3 连接池 + 编号 SQL 迁移（`backend/migrations/postgres/NNNN_*.sql`）+ JWT/bcrypt |
| 数据 | PostgreSQL 16（含 `earthdistance` 做附近房源）、Redis 7 |
| 定时 | APScheduler（租约状态推进、订阅匹配补偿） |
| AI | 沿用其 OpenAI 兼容配置（`LLM_PROVIDER` / `OPENAI_BASE_URL` / `CHAT_MODEL_NAME`） |
| 推送 | 站内 SSE 实时通知 + 浏览器通知（PWA）+ 邮件；Telegram/Webhook 可选 |

保留的 AIGCNEWS 后端底层（7 个模块，约 1500 行）：`core/config`、`core/auth`、`core/postgres_database`、`core/postgres_migrations`、`core/redis_client`、`domain/membership`、`repositories/user_account_repository`。业务接口全部按找房重写（原 `routes_auth` 一个文件就牵出 300+ 个新闻业务模块，不可复用）。

## 2. 角色

| 角色 | 说明 |
|---|---|
| 访客 | 不登录也能找房、看详情、地图找房、提交咨询 |
| 租客用户 | 登录后：收藏、房源订阅（实时推送）、AI 找房历史 |
| 房东（租户管理员）/ 房东员工 | 房东后台：房源、出租、收租、咨询；员工按权限 |
| 平台管理员 | 查看/编辑/停用房东、审核房源、只读进入房东后台 |
| 超级管理员 | 全部 |

数据隔离：所有业务表带 `tenant_id`，后端仓储层统一按当前房东过滤；公开接口只放出「已上架 + 可租 + 房东正常」的房源。

## 3. 找房前台

导航（参照 AIGCNEWS 首页：报头 + 统计卡 + 分类标签 + 卡片榜单 + 右侧栏 + 底部导航）：

- 报头口号：**房子 / 发现更好的房源 / 让找房更便捷**；板块标题「今日房源动态」（英文：Houses / Discover better listings / Make house hunting easier / Today's property updates）
- 分类标签：**全部 · 长租 · 短租 · 合租**（+ 整租/单间等常规筛选）
- 筛选：城市/区域、租金区间、户型（室厅卫）、面积、朝向、装修、配套、可入住日期、**租住日期区间（入住~退租，只显示该区间可租的房源）**
- 房源以 **UI 卡片** 展示：封面、标题、租金（长租月租 / 短租日租）、户型面积、标签、距离
- **AI 一键找房**：输入「西湖区两室一厅 3000 以内 下个月入住 住半年」→ LLM 解析为结构化条件（失败时规则解析兜底）→ 返回卡片 + 匹配理由
- **地图找房**：Leaflet + OSM，按视野加载房源点，点选看卡片
- **附近房源**：浏览器定位或地图选点，按距离排序
- **推荐房源**：新上架、性价比、与当前浏览相似
- **房源订阅**：保存条件（也可由 AI 找房一键转订阅），新房源上架/降价时匹配，**实时推送**（站内 + 浏览器通知 + 邮件）
- 右侧栏：日历（今日新上架回看）、热门区域、订阅入口

## 4. 分阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P0 骨架** | 清理新闻业务；后端保留底层 + 新 `main.py` + 健康检查 + 注册登录；新迁移 `0001`；前端保留外壳/主题/i18n，换 Houses 品牌与口号，首页占位；本地 Docker（PG+Redis）可启动 | 前后端能跑、能注册登录、页面是 Houses 品牌 |
| **P1 房源与前台找房** | 房东/小区/楼栋/房间/图片表（含长租/短租/合租、日租价、最短租期、经纬度）；公开接口：列表筛选、日期可租、详情、附近、推荐；前台首页卡片、筛选、详情页、地图找房 | 访客能按分类/日期/区域找房、看地图和附近 |
| **P2 房东后台** | 多房东（租户）与员工权限、平台/超级管理员；房源增删改、上下架、审核；咨询管理 | 房东只看到自己的数据；平台能管房东 |
| **P3 出租与收租（只记账）** | 移植 ruoyi 版业务：签约一次出账（BillPlanner）、收款/减免/冲正（BillLedger）、抄表出账、退租结算、每日状态任务；**把 Java 单元测试移植为 pytest** | 规则与 ruoyi 版一致，测试全绿 |
| **P4 AI 找房与订阅推送** | 自然语言解析、匹配理由；订阅条件、上架/降价触发匹配、SSE 实时推送 + 浏览器通知 + 邮件 | 新房源上架后订阅用户实时收到通知 |
| **P5 打磨与上线** | 中英文、手机布局、PWA、SEO、AGPL 源码链接、部署 | 上线前清单通过 |

## 进度记录

- **2026-10-17 P0 完成**：注册/登录、Houses 外壳与首页（中英文、深色、PWA）。
- **2026-10-17 P1 完成**：
  - 迁移 `0002_listings.sql`：landlords / estates / listings / listing_images / listing_unavailability / listing_inquiries，全部带 landlord_id，供 P2 隔离。
  - 检索规则集中在 `backend/app/domain/listing_search.py`：可租判断用半开区间 [入住, 退租)；长租的退租日 = 入住日 + N 个自然月（月末对齐）；同时校验最短租期 / 最短晚数。
  - 接口：`GET /api/listings`（筛选/分页/附近）、`/api/listings/map`（bbox）、`/home`、`/facets`、`/{id}`、`POST /{id}/inquiries`（按 IP 和手机号用 Redis 限流）。
  - 前端：找房列表（筛选与 URL 双向同步）、详情 + 咨询表单、Leaflet + OSM 地图找房（按小区合并标记）；首页接真实接口。
  - 演示数据：`backend/.venv/Scripts/python -m backend.scripts.seed_demo`，可重复执行。
  - 测试：pytest 45 个，vitest 7 个。
- **2026-10-17 P2 完成**：
  - 迁移 `0003_landlord_console.sql`：landlord_members 表（一个账号只属于一个房东，角色分 owner / staff），咨询表加跟进备注和处理时间。
  - 权限依赖：`RequireLandlord` 从登录账号查出 landlord_id，房东停用后立即返回 403；`RequireLandlordOwner` 只给主账号用（管理成员）。
  - 隔离：所有房东接口的查询都带 landlord_id 条件，访问别家的数据一律返回 404。
  - 房东接口 `/api/landlord/*`：概览、小区（小区下有房源时不能删）、房源（上下架、上架中不能删）、图片（按文件头判断真实格式，单张不超过 5MB，每套最多 12 张，首图作封面）、不可租时段、咨询、成员。
  - 平台接口 `/api/admin/*`：开通、停用、启用房东，房源强制下架和设为推荐。
  - `/api/auth/me` 和登录返回里带上 `landlord`，前端据此显示后台入口。
  - 前端：房东后台（概览、房源列表、编辑器、小区地图选点、咨询跟进、成员）；平台管理（房东、房源审核）；没登录或没权限时页面内给出提示。
  - 图片存在 `data/uploads`（可通过 UPLOAD_DIR 配置），经 `/uploads` 对外提供。
  - 测试：pytest 61 个（P2 新增 16 个，覆盖越权访问），vitest 10 个。

## 收租边界（2026-10-17 确认）

平台**不做实际收款，只做记录**：
- 不接任何支付通道（微信/支付宝/银行），租客端没有付款入口，不存银行卡等支付信息。
- 「收款」= 房东线下收到钱后手动登记一笔流水；收款方式（现金、微信、支付宝、转账）只是标签。
- 退押金同样只记录一笔负数流水，实际退款由房东线下完成。
- 账单、明细、流水只作废不删除，保留完整记账痕迹。
- **2026-10-17 P3 完成（只记账）**：
  - 迁移 `0004_leasing.sql`：renters（只存证件号末 4 位）、fee_items、leases、lease_fees、bills、bill_items、meter_readings、payments。
  - 纯计算规则 `backend/app/domain/billing.py`：从 ruoyi 版 BillPlanner / BillLedger 移植，24 个 Java 单测已改写为 pytest（`tests/test_billing_unit.py`）。
  - 签约：同一份请求先预览、再签约，一次生成押金账单和全部租金账单；写入「已出租」时段；已上架的房源自动下架；从咨询发起签约时，该咨询自动关闭。
  - 收款只登记：手工登记的收款方式限 现金 / 微信 / 支付宝 / 转账 / 其他；押金抵扣、退押金只能由退租结算自动生成。账单行加锁更新；作废收款时冲回已收金额。
  - 抄表：上次读数自动带出；单价优先用租约约定价；费用立即记入「账期开始日不早于抄表日」的最近一张未结清租金账单，没有就单独出一张。
  - 退租：先解绑抄表，再作废未来未收的账单；生成结算单；押金按应收日先后抵扣；剩余部分记为退押金负数流水；已出租时段截到退租日。
  - 每日任务：APScheduler 在启动时跑一次，之后每天 00:05 推进租约状态（待生效 → 生效中 → 已到期）。
  - 前端：租约列表、签约（带账单预览）、租约详情（账单、抄表、退租）、账单页（统计、逾期、收款流水）、设置页（收费项目、租客）。
  - 测试：pytest 99 个，vitest 16 个。
- **2026-10-17 P4 完成**：
  - AI 找房：`domain/ai_search.py` 规则解析，能识别预算区间（k、千、万、左右）、中文数字居室、租期、日期区间、入住晚数、区域简称、标签同义词，只匹配库里已有的值。`core/llm.py` 调 OpenAI 兼容接口，结果按白名单校验，失败时回退规则解析，并用规则结果补全缺失字段。
  - 没有结果时先尝试「只放宽一项」，尽量保留用户的其他要求；都不行再叠加放宽。按 IP 限流：每 10 分钟 30 次。
  - 订阅：迁移 `0005_subscriptions.sql`。条件就是 `/api/listings` 的参数，匹配时复用公开检索的 SQL；每个用户最多 10 个订阅。
  - 通知：房源上架、降价（同一计价单位下）时后台匹配；同一订阅、同一房源、同一事件、同一价格只通知一次，靠唯一约束保证；补偿任务每 10 分钟跑一次。
  - 推送：SSE 走 Redis pub/sub，没有 Redis 时退化为进程内广播；前端用 fetch 读取流，断线退避重连，每分钟轮询未读数兜底；页面在后台时弹浏览器通知；配置 SMTP 后发邮件。
  - 前端：AI 找房页（条件标签可删、显示匹配理由、显示放宽了什么）、订阅页（复用找房筛选栏、收件箱）、顶栏铃铛（未读数 + 实时连接状态）。
  - 测试：pytest 137 个，vitest 20 个。
- **2026-10-17 P5 完成（本地部分）**：
  - SEO：`features/seo/pageHead.ts` 按路由设置标题、描述，后台页面加 noindex；房源详情页输出 schema.org `Apartment` JSON-LD；后端 `/sitemap.xml` 列出公开页面和所有上架房源；robots.txt 屏蔽 `/landlord`、`/admin`、`/subscriptions`、`/api/`。
  - 页面：正式的关于页、隐私政策页（写明只记账不收款、个人信息范围、第三方服务）。
  - 安全：后端安全头（纯 ASGI 中间件，不影响 SSE），nginx 严格 CSP（主题初始化脚本移出 index.html，不允许内联脚本）；注册按 IP 每小时 10 次；生产环境不暴露接口文档；`ENVIRONMENT=production` 时启动自检（源码地址、https、CORS、密码长度、Redis 密码）。
  - 运维：健康检查同时探测数据库；统一日志格式；`docker-compose.yml`（postgres / redis / api / web）、`deploy/.env.production.example`、`deploy/backup.sh`。
  - 清理：删除 AIGCNEWS 的 deploy、docker、scripts 目录和旧 Dockerfile；重写 README、AGENTS.md、CLAUDE.md；NOTICE 写明派生关系，并保留上游声明。
  - 验证：用生产配置在本地 docker compose 起全套服务冒烟测试，健康检查、安全头、CSP 下地图正常、SSE 经 nginx 不缓冲都确认通过。pytest 149 个，vitest 20 个。
  - 待用户提供：服务器、域名、公开源码仓库地址后再正式部署。
