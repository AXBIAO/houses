import { reactive } from 'vue'
import { api } from '@/services/http/apiClient'

/** AGPL-3.0 §13：向网络用户提供源码链接。地址由后端 SOURCE_CODE_URL 配置，前端兜底到本项目仓库。 */
const FALLBACK_SOURCE_URL = 'https://github.com/AXBIAO/houses'

interface SiteInfo {
  name: string
  license: string
  sourceCodeUrl: string
  /** 高德地图 Web 端 Key，空表示用 OpenStreetMap */
  amapKey: string
  /** 已拿到后端结果（或请求失败）；地图要等它决定用哪家底图 */
  ready: boolean
}

const site = reactive<SiteInfo>({ name: 'Houses', license: 'AGPL-3.0', sourceCodeUrl: FALLBACK_SOURCE_URL, amapKey: '', ready: false })
let loaded = false

export function useSiteInfo(): Readonly<SiteInfo> {
  if (!loaded) {
    loaded = true
    api.get<Omit<SiteInfo, 'ready'>>('/api/site')
      .then((info) => {
        site.name = info.name
        site.license = info.license
        if (info.sourceCodeUrl) site.sourceCodeUrl = info.sourceCodeUrl
        site.amapKey = info.amapKey ?? ''
      })
      .catch(() => { loaded = false })
      .finally(() => { site.ready = true })
  }
  return site
}
