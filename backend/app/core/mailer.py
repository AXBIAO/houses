"""订阅通知邮件。未配置 SMTP 时直接跳过；发送失败只记日志，不影响站内通知。"""
from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from backend.app.services.runtime_config import SmtpConfig

logger = logging.getLogger("houses.mailer")


async def deliver(to: str, subject: str, text: str, config: SmtpConfig) -> str | None:
    """发送成功返回 None，失败返回原因（后台「发送测试邮件」直接展示）。"""
    if not config.enabled:
        return "请先填写 SMTP 服务器与发件地址"
    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    try:
        # use_tls：465 端口直接 TLS；否则（如 587）由服务器支持情况自动 STARTTLS
        await aiosmtplib.send(
            message, hostname=config.host, port=config.port, username=config.user or None,
            password=config.password or None, use_tls=config.use_tls, start_tls=False if config.use_tls else None, timeout=15,
        )
        return None
    except (aiosmtplib.SMTPException, OSError) as exc:
        return f"{type(exc).__name__}: {exc}"


async def send_mail(to: str, subject: str, text: str, config: SmtpConfig) -> bool:
    if not config.enabled:
        return False
    error = await deliver(to, subject, text, config)
    if error:
        logger.warning("通知邮件发送失败 %s：%s", to, error)
    return error is None
