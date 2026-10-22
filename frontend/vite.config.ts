// Modified for Houses (based on AIGCNEWS, AGPL-3.0)
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  server: {
    port: 5180,
    proxy: {
      '/api': { target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8020', changeOrigin: true },
      '/uploads': { target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8020', changeOrigin: true },
      '/robots.txt': { target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8020', changeOrigin: true },
      '/sitemap.xml': { target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8020', changeOrigin: true },
      // 本地开发的高德安全密钥代理，与生产 nginx 的 /_AMapService 行为一致；密钥从环境变量 AMAP_SECURITY_CODE 读取
      '/_AMapService': {
        target: 'https://restapi.amap.com',
        changeOrigin: true,
        rewrite: path => {
          const url = new URL(path.replace(/^\/_AMapService/, ''), 'http://x')
          url.searchParams.set('jscode', process.env.AMAP_SECURITY_CODE ?? '')
          return url.pathname + url.search
        },
      },
    },
  },
  plugins: [
    vue(),
    // 注册由 src/pwa/registerPwa.ts 手动完成；manifest 用 public/ 下手写版。/api 不经 Service Worker（SSE + JWT）。
    VitePWA({
      injectRegister: false,
      manifest: false,
      registerType: 'autoUpdate',
      workbox: {
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/uploads\//, /^\/_AMapService\//],
        clientsClaim: true,
        skipWaiting: true,
        globPatterns: ['**/*.{js,css,html,mjs,png,svg,ico,woff,woff2}'],
      },
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    exclude: ['**/node_modules/**', '**/dist/**'],
  },
})
