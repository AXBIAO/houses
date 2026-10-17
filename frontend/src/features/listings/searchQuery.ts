import type { LocationQuery } from 'vue-router'
import { RENT_TYPES, SORT_KEYS, type RentType, type SortKey } from './types'

type QueryValue = LocationQuery[string] | undefined

/** 找房条件。URL 参数名与后端 /api/listings 完全一致，页面之间、页面与接口之间都用同一套。 */
export interface SearchState {
  type: RentType | null
  q: string
  district: string
  minPrice: number | null
  maxPrice: number | null
  bedrooms: number | null
  tags: string[]
  moveIn: string
  moveOut: string
  months: number | null
  recommended: boolean
  sort: SortKey
}

export const EMPTY_SEARCH: Readonly<SearchState> = Object.freeze({
  type: null, q: '', district: '', minPrice: null, maxPrice: null, bedrooms: null,
  tags: [], moveIn: '', moveOut: '', months: null, recommended: false, sort: 'latest',
})

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

function first(value: QueryValue): string {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw.trim() : ''
}

function int(value: QueryValue, min: number, max: number): number | null {
  const n = Number.parseInt(first(value), 10)
  return Number.isFinite(n) && n >= min && n <= max ? n : null
}

function oneOf<T extends string>(value: QueryValue, options: readonly T[]): T | null {
  const raw = first(value)
  return (options as readonly string[]).includes(raw) ? raw as T : null
}

/** 解析 URL；非法值丢弃而不是报错，避免分享出去的旧链接打不开。 */
export function parseSearch(query: LocationQuery): SearchState {
  const date = (v: QueryValue) => (DATE_RE.test(first(v)) ? first(v) : '')
  return {
    type: oneOf(query.type, RENT_TYPES),
    q: first(query.q).slice(0, 100),
    district: first(query.district).slice(0, 30),
    minPrice: int(query.minPrice, 0, 1_000_000),
    maxPrice: int(query.maxPrice, 0, 1_000_000),
    bedrooms: int(query.bedrooms, 0, 20),
    tags: first(query.tags).split(',').map(t => t.trim()).filter(Boolean).slice(0, 8),
    moveIn: date(query.moveIn),
    moveOut: date(query.moveOut),
    months: int(query.months, 1, 36),
    recommended: first(query.recommended) === 'true',
    sort: oneOf(query.sort, SORT_KEYS) ?? 'latest',
  }
}

/** 序列化为 URL / 接口参数：只写非默认值；短租用退租日，其余用月数。 */
export function toQuery(state: SearchState): Record<string, string> {
  const out: Record<string, string> = {}
  const isShort = state.type === 'short'
  if (state.type) out.type = state.type
  if (state.q.trim()) out.q = state.q.trim()
  if (state.district) out.district = state.district
  if (state.minPrice != null) out.minPrice = String(state.minPrice)
  if (state.maxPrice != null) out.maxPrice = String(state.maxPrice)
  if (state.bedrooms != null) out.bedrooms = String(state.bedrooms)
  if (state.tags.length) out.tags = state.tags.join(',')
  if (state.moveIn) out.moveIn = state.moveIn
  if (isShort && state.moveOut) out.moveOut = state.moveOut
  if (!isShort && state.months != null) out.months = String(state.months)
  if (state.recommended) out.recommended = 'true'
  if (state.sort !== 'latest') out.sort = state.sort
  return out
}

export function withChanges(state: SearchState, changes: Partial<SearchState>): SearchState {
  return { ...state, ...changes, tags: [...(changes.tags ?? state.tags)] }
}

export function isFiltered(state: SearchState): boolean {
  const { sort: _sort, ...rest } = toQuery(state)
  return Object.keys(rest).length > 0
}
