import type { Router } from 'vue-router'
import { i18n } from '@/i18n'

export interface PageHead {
  title?: string
  description?: string
  noindex?: boolean
}

const JSON_LD_ID = 'page-jsonld'

function setMeta(attr: 'name' | 'property', key: string, content: string | null) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (content === null) {
    el?.remove()
    return
  }
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

/** 设置标题、描述、Open Graph 与 robots。标题统一带站名后缀。 */
export function setPageHead(head: PageHead): void {
  const t = i18n.global.t
  const brand = t('brand.name')
  const title = head.title ? `${head.title} · ${brand}` : `${brand} · ${t('brand.slogan')}`
  const description = head.description ?? t('seo.defaultDescription')
  document.title = title
  setMeta('name', 'description', description)
  setMeta('property', 'og:title', title)
  setMeta('property', 'og:description', description)
  setMeta('name', 'robots', head.noindex ? 'noindex, nofollow' : null)
}

/** 结构化数据（如房源详情的 Apartment）；传 null 清除。 */
export function setJsonLd(data: Record<string, unknown> | null): void {
  document.getElementById(JSON_LD_ID)?.remove()
  if (!data) return
  const script = document.createElement('script')
  script.type = 'application/ld+json'
  script.id = JSON_LD_ID
  script.textContent = JSON.stringify(data)
  document.head.appendChild(script)
}

declare module 'vue-router' {
  interface RouteMeta {
    titleKey?: string
    descriptionKey?: string
    noindex?: boolean
    /** 页面自己设置标题（如房源详情），路由切换时不覆盖 */
    customHead?: boolean
  }
}

/** 路由切换时按 meta 更新页面头；详情页等动态页面自行调用 setPageHead。 */
export function installPageHead(router: Router): void {
  router.afterEach((to) => {
    setJsonLd(null)
    if (to.meta.customHead) return
    const t = i18n.global.t
    setPageHead({
      title: to.meta.titleKey ? t(to.meta.titleKey) : undefined,
      description: to.meta.descriptionKey ? t(to.meta.descriptionKey) : undefined,
      noindex: to.meta.noindex,
    })
  })
}
