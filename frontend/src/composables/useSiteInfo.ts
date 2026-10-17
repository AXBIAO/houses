import { reactive } from 'vue'
import { api } from '@/services/http/apiClient'

/** AGPL-3.0 §13：向网络用户提供源码链接。地址由后端 SOURCE_CODE_URL 配置，前端兜底到本项目仓库。 */
const FALLBACK_SOURCE_URL = 'https://github.com/AXBIAO/houses'

interface SiteInfo {
  name: string
  license: string
  sourceCodeUrl: string
}

const site = reactive<SiteInfo>({ name: 'Houses', license: 'AGPL-3.0', sourceCodeUrl: FALLBACK_SOURCE_URL })
let loaded = false

export function useSiteInfo(): Readonly<SiteInfo> {
  if (!loaded) {
    loaded = true
    api.get<SiteInfo>('/api/site')
      .then((info) => {
        site.name = info.name
        site.license = info.license
        if (info.sourceCodeUrl) site.sourceCodeUrl = info.sourceCodeUrl
      })
      .catch(() => { loaded = false })
  }
  return site
}
