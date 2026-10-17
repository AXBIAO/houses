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
        navigateFallbackDenylist: [/^\/api\//, /^\/uploads\//],
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
