"""Houses API 入口。底层设施（配置、PostgreSQL 连接池与迁移、JWT 鉴权、Redis）沿用 AIGCNEWS（AGPL-3.0）。"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api import (
    routes_admin,
    routes_ai,
    routes_auth,
    routes_bills,
    routes_health,
    routes_landlord,
    routes_landlord_listings,
    routes_leasing,
    routes_listings,
    routes_settings,
    routes_sitemap,
    routes_subscriptions,
)
from backend.app.core.auth import ROLE_SUPERADMIN, hash_password, validate_jwt_secret
from backend.app.core.config import settings
from backend.app.core.http_security import SecurityHeadersMiddleware
from backend.app.core.logging_setup import configure_logging
from backend.app.core.production_checks import assert_production_ready
from backend.app.core.media import upload_root
from backend.app.core.postgres_database import postgres_database
from backend.app.core.postgres_migrations import PostgresMigrationRunner
from backend.app.core.redis_client import close_redis_client, create_redis_client
from backend.app.domain.errors import DomainError
from backend.app.repositories.app_settings import AppSettingsRepository
from backend.app.repositories.bills import BillRepository
from backend.app.repositories.checkout import CheckoutRepository
from backend.app.repositories.estates import EstateRepository
from backend.app.repositories.inquiries import InquiryRepository
from backend.app.repositories.landlords import LandlordRepository
from backend.app.repositories.leases import LeaseRepository
from backend.app.repositories.listing_admin import ListingAdminRepository
from backend.app.repositories.listings import ListingRepository
from backend.app.repositories.meters import MeterRepository
from backend.app.repositories.renters import RenterRepository
from backend.app.repositories.subscriptions import SubscriptionRepository
from backend.app.repositories.users import UserRepository
from backend.app.services.notifier import NotificationHub, match_recent
from backend.app.services.runtime_config import RuntimeConfig

logger = logging.getLogger("houses")


def _bootstrap_superadmin(users: UserRepository) -> None:
    """库里还没有超级管理员、且环境变量提供了账号时创建一个。"""
    email, password = settings.bootstrap_admin_email, settings.bootstrap_admin_password
    if not email or not password or users.has_role(ROLE_SUPERADMIN):
        return
    if users.exists(email=email, phone=None):
        logger.warning("bootstrap admin %s 已存在但不是超级管理员，跳过", email)
        return
    users.create_user(email=email, phone=None, username="超级管理员", password_hash=hash_password(password),
                      role=ROLE_SUPERADMIN)
    logger.info("已创建超级管理员 %s", email)


async def _connect_redis(app: FastAPI) -> None:
    client = create_redis_client(decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=3)
        app.state.redis = client
    except Exception as exc:  # 本地开发允许没有 Redis，登录限流随之关闭
        logger.warning("Redis 不可用，登录限流已关闭：%s", exc)
        await close_redis_client(client)
        app.state.redis = None


async def _advance_leases(app: FastAPI) -> None:
    try:
        counts = await asyncio.to_thread(app.state.leases.advance_statuses, date.today())
        if any(counts.values()):
            logger.info("租约状态推进：%s", counts)
    except Exception:  # 定时任务失败不影响服务，下次再跑
        logger.exception("租约状态推进失败")


async def _match_recent(app: FastAPI) -> None:
    """订阅匹配补偿：上架时的后台匹配若因异常丢失，这里会补上（通知有唯一约束，不会重复）。"""
    try:
        created = await match_recent(app.state, minutes=30)
        if created:
            logger.info("订阅补偿匹配新增通知 %s 条", created)
    except Exception:
        logger.exception("订阅补偿匹配失败")


async def _start_scheduler(app: FastAPI) -> AsyncIOScheduler | None:
    """启动时先推进一次，之后每天 00:05 再推进；可重复执行，不怕漏跑或重跑。"""
    await _advance_leases(app)
    if not settings.scheduler_enabled:
        return None
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_advance_leases, CronTrigger(hour=0, minute=5), args=[app], id="advance-leases",
                      coalesce=True, max_instances=1)
    scheduler.add_job(_match_recent, IntervalTrigger(minutes=10), args=[app], id="match-subscriptions",
                      coalesce=True, max_instances=1)
    scheduler.start()
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    validate_jwt_secret(settings.JWT_SECRET_KEY)
    assert_production_ready(settings)
    await asyncio.to_thread(postgres_database.open)
    if settings.postgres_auto_migrate:
        applied = await asyncio.to_thread(PostgresMigrationRunner(postgres_database).apply)
        for migration in applied:
            logger.info("已应用迁移 %s", migration.filename)
    app.state.users = UserRepository(postgres_database)
    app.state.listings = ListingRepository(postgres_database)
    app.state.landlords = LandlordRepository(postgres_database)
    app.state.estates = EstateRepository(postgres_database)
    app.state.listing_admin = ListingAdminRepository(postgres_database)
    app.state.inquiries = InquiryRepository(postgres_database)
    app.state.renters = RenterRepository(postgres_database)
    app.state.leases = LeaseRepository(postgres_database)
    app.state.bills = BillRepository(postgres_database)
    app.state.meters = MeterRepository(postgres_database)
    app.state.checkout = CheckoutRepository(postgres_database)
    app.state.subscriptions = SubscriptionRepository(postgres_database)
    app.state.app_settings = AppSettingsRepository(postgres_database)
    app.state.runtime = RuntimeConfig(app.state.app_settings)
    await asyncio.to_thread(_bootstrap_superadmin, app.state.users)
    await _connect_redis(app)
    app.state.hub = NotificationHub(app.state.redis)
    scheduler = await _start_scheduler(app)
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if app.state.redis is not None:
            await close_redis_client(app.state.redis)
        await asyncio.to_thread(postgres_database.close)


def create_app() -> FastAPI:
    configure_logging()
    production = settings.environment.lower() == "production"
    # 生产环境不暴露接口文档
    app = FastAPI(title="Houses API", lifespan=lifespan,
                  docs_url=None if production else "/docs", redoc_url=None, openapi_url=None if production else "/openapi.json")
    app.add_middleware(SecurityHeadersMiddleware, hsts=production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_health.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_listings.router)
    app.include_router(routes_landlord.router)
    app.include_router(routes_landlord_listings.router)
    app.include_router(routes_leasing.router)
    app.include_router(routes_bills.router)
    app.include_router(routes_ai.router)
    app.include_router(routes_subscriptions.router)
    app.include_router(routes_admin.router)
    app.include_router(routes_sitemap.router)
    app.include_router(routes_settings.router)

    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    uploads = upload_root()
    uploads.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads), name="uploads")
    return app


app = create_app()
