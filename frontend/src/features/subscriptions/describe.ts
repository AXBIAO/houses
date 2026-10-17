import { parseSearch } from '@/features/listings/searchQuery'

type Translate = (key: string, values?: Record<string, unknown>) => string

/** 把订阅保存的条件（/api/listings 参数）转成可读标签。 */
export function describeFilters(filters: Record<string, string>, t: Translate): string[] {
  const s = parseSearch(filters)
  const unit = s.type === 'short' ? t('common.perNight') : t('common.perMonth')
  const out: string[] = []
  if (s.type) out.push(t(`rentType.${s.type}`))
  if (s.district) out.push(s.district)
  if (s.q) out.push(`「${s.q}」`)
  if (s.minPrice != null && s.maxPrice != null) out.push(`¥${s.minPrice}–${s.maxPrice}${unit}`)
  else if (s.maxPrice != null) out.push(t('filters.priceUnder', { n: s.maxPrice }) + unit)
  else if (s.minPrice != null) out.push(t('filters.priceOver', { n: s.minPrice }) + unit)
  if (s.bedrooms != null) out.push(t('filters.bedroomsPlus', { n: s.bedrooms }))
  out.push(...s.tags)
  if (s.moveIn) out.push(t('subs.moveInOn', { date: s.moveIn }))
  if (s.months != null && s.type !== 'short') out.push(t('home.months', { n: s.months }))
  return out
}
