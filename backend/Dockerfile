# Houses API。构建上下文为 backend/，代码放在 /app/backend 以保持 `backend.app.*` 绝对导入。
FROM python:3.11-slim

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --index-url "$PIP_INDEX_URL" -r /tmp/requirements.txt \
    && useradd --create-home --uid 10001 houses \
    && mkdir -p /data/uploads && chown houses:houses /data/uploads

COPY --chown=houses:houses . /app/backend
USER houses

ENV UPLOAD_DIR=/data/uploads
EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8020/api/health', timeout=4).status == 200 else 1)"

# 只在 nginx 之后运行：信任反向代理传来的客户端 IP（限流按真实 IP 计）
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8020", "--proxy-headers", "--forwarded-allow-ips", "*"]
