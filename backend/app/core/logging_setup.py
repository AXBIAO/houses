"""统一日志格式：时间、级别、模块、内容，方便 docker logs 与日志采集。"""
from __future__ import annotations

import logging
import os

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format=FORMAT)
    # 访问日志交给 nginx；保留 uvicorn 的错误日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
