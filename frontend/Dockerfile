# Houses 前端：Node 构建静态文件，nginx 提供页面并反向代理 API。
FROM node:22-alpine AS build
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --registry="$NPM_REGISTRY" --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY nginx-amap-proxy.conf /etc/nginx/snippets/amap-proxy.conf
COPY nginx-amap.conf.template /etc/nginx/templates/amap.conf.template
# 未配置高德时渲染为空密钥，/_AMapService 直接 404，前端用 OpenStreetMap
ENV AMAP_SECURITY_CODE=""
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/healthz || exit 1
