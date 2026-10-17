import { ref } from 'vue'
import { listingsApi } from './api'
import type { Facets } from './types'

const facets = ref<Facets | null>(null)
let pending: Promise<void> | null = null

/** 区域与热门标签在多个页面共用，进程内只取一次；失败后允许下次重试。 */
export function useFacets() {
  if (!facets.value && !pending) {
    pending = listingsApi.facets()
      .then((value) => { facets.value = value })
      .catch(() => undefined)
      .finally(() => { pending = null })
  }
  return facets
}
