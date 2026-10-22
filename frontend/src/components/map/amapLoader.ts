import AMapLoader from '@amap/amap-jsapi-loader'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AMapNamespace = any

/** 安全密钥由 web 容器的 nginx 在 /_AMapService 上拼接（见 frontend/nginx.conf），浏览器里只出现 Key。 */
const SERVICE_PATH = '/_AMapService'

let pending: Promise<AMapNamespace> | null = null

/** 整个页面只加载一次 JS API；失败后清空缓存，允许下次重试。 */
export function loadAMap(key: string): Promise<AMapNamespace> {
  if (!pending) {
    ;(window as unknown as { _AMapSecurityConfig: { serviceHost: string } })._AMapSecurityConfig = {
      serviceHost: `${window.location.origin}${SERVICE_PATH}`,
    }
    pending = AMapLoader.load({ key, version: '2.0', plugins: ['AMap.Scale', 'AMap.ToolBar'] })
      .catch((error: unknown) => {
        pending = null
        throw error
      })
  }
  return pending
}
