# Modified for Houses (based on AIGCNEWS, AGPL-3.0): trimmed to the settings the rental platform uses.
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 站点
    app_name: str = "Houses"
    environment: str = "development"
    # AGPL-3.0 §13：通过网络提供服务时须向用户提供对应源码，页脚链接到此地址
    source_code_url: str = ""
    # 高德地图 JS API 的 Web 端 Key（公开下发给浏览器）；安全密钥只配在 web 容器的 nginx 代理里，不经过后端
    amap_key: str = ""
    # 浏览器直连 API 的前端来源（逗号分隔）
    cors_allowed_origins: str = "http://localhost:5180,http://127.0.0.1:5180"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_database: str = ""
    postgres_sslmode: str = "disable"
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 10
    postgres_pool_timeout_seconds: float = 10.0
    postgres_connect_timeout_seconds: int = 5
    postgres_statement_timeout_ms: int = 15_000
    # 启动时自动执行未应用的迁移（生产可关闭，改由发布流程执行）
    postgres_auto_migrate: bool = True

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # JWT 鉴权（密钥必须由环境提供，缺失或过短拒绝启动）
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 天

    # 首次启动时创建的超级管理员（库里已有超管则忽略）
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    # 房源图片：本地目录，经 /uploads 对外提供（相对路径以项目根目录为基准）
    upload_dir: str = "data/uploads"
    upload_max_bytes: int = 5 * 1024 * 1024
    listing_max_images: int = 12

    # 站点对外地址：通知邮件里的房源链接
    public_base_url: str = "http://127.0.0.1:5180"

    # 订阅通知邮件（不配置则只做站内与浏览器通知）
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # 定时任务（租约状态每日推进）；测试或多实例部署时可关闭
    scheduler_enabled: bool = True

    # 大模型（OpenAI 兼容接口），用于 AI 一键找房
    openai_base_url: str = ""
    openai_api_key: str = ""
    chat_model_name: str = ""
    llm_request_timeout: float = 30.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
