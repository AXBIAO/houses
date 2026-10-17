# Houses 开发约定（给 AI 编码助手与贡献者）

## 边界

- **平台只记账，不收款**：不接任何支付通道，不收集支付信息；收款、退押金都是房东手动登记的流水。
- **房东数据隔离**：房东后台的每条 SQL 都必须带 `landlord_id` 条件；越权访问一律返回 404（不暴露是否存在）。新增接口要在测试里覆盖「另一个房东访问」。
- **AGPL-3.0**：页脚源码链接不能去掉；不得使用 AIGCNEWS 品牌素材（名称、Logo、插画、icons）。改动沿用自 AIGCNEWS 的文件时保留 `Modified for Houses (based on AIGCNEWS, AGPL-3.0)` 注释。
- **个人信息最少化**：证件号只存末 4 位；咨询手机号只给对应房东。

## 代码

- 后端：路由薄、仓储做数据访问、`domain/` 放纯函数规则（计费、检索、AI 解析）并配单测。金额用 `Decimal` / `numeric`，财务表只作废不删除。
- 数据库变更只加新的编号迁移（`backend/migrations/postgres/000N_*.sql`），不改已发布的迁移。
- 前端：新增文案必须同时写 `zh-CN.ts` 与 `en-US.ts`；筛选条件统一用 `features/listings/searchQuery.ts` 与 URL 互转。
- 在应用自己的事件循环里调用异步代码（测试里用 `client.portal.call`），不要 `asyncio.run`：Redis 连接绑定在应用循环上。

## 验证

```bash
backend/.venv/Scripts/python -m pytest backend/tests
cd frontend && npm run typecheck && npm run test:unit && npm run build
```

提交信息遵循 Conventional Commits：`<type>(<scope>): <subject>`。
