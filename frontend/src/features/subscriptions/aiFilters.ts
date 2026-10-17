/** AI 识别出的条件标签 key → 对应的 /api/listings 参数，删除标签时同步删掉参数。 */
export function withoutCondition(filters: Record<string, string>, key: string): Record<string, string> {
  const next = { ...filters }
  if (key.startsWith('tag:')) {
    const tag = key.slice(4)
    const tags = (next.tags ?? '').split(',').filter(t => t && t !== tag)
    if (tags.length) next.tags = tags.join(',')
    else delete next.tags
    return next
  }
  const map: Record<string, string[]> = {
    type: ['type', 'moveOut'], district: ['district'], q: ['q'], price: ['minPrice', 'maxPrice'], bedrooms: ['bedrooms'],
    moveIn: ['moveIn', 'moveOut'], moveOut: ['moveOut'], months: ['months'], near: ['lat', 'lng', 'radiusKm', 'sort'],
  }
  for (const param of map[key] ?? []) delete next[param]
  return next
}

/** 订阅只保存可长期匹配的条件，位置类参数不保存。 */
export function subscribableFilters(filters: Record<string, string>): Record<string, string> {
  const { lat: _lat, lng: _lng, radiusKm: _r, sort: _s, ...rest } = filters
  return rest
}
