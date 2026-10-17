import { describe, expect, it } from 'vitest'
import { EMPTY_SEARCH, isFiltered, parseSearch, toQuery, withChanges } from './searchQuery'

describe('parseSearch', () => {
  it('parses valid params', () => {
    const state = parseSearch({ type: 'short', q: ' 江景 ', minPrice: '200', tags: '近地铁, 江景', moveIn: '2026-11-01', moveOut: '2026-11-03', sort: 'price_asc' })
    expect(state).toMatchObject({ type: 'short', q: '江景', minPrice: 200, tags: ['近地铁', '江景'], moveIn: '2026-11-01', moveOut: '2026-11-03', sort: 'price_asc' })
  })

  it('drops invalid values instead of failing', () => {
    const state = parseSearch({ type: 'villa', minPrice: '-5', months: '99', moveIn: 'tomorrow', sort: 'random' })
    expect(state).toEqual({ ...EMPTY_SEARCH })
  })

  it('takes the first value of repeated params', () => {
    expect(parseSearch({ type: ['long', 'short'] }).type).toBe('long')
  })
})

describe('toQuery', () => {
  it('omits defaults', () => {
    expect(toQuery(EMPTY_SEARCH)).toEqual({})
    expect(isFiltered(withChanges(EMPTY_SEARCH, { sort: 'price_desc' }))).toBe(false)
  })

  it('keeps move-out only for short stays and months only for leases', () => {
    const base = withChanges(EMPTY_SEARCH, { moveIn: '2026-11-01', moveOut: '2026-11-05', months: 6 })
    expect(toQuery({ ...base, type: 'short' })).toEqual({ type: 'short', moveIn: '2026-11-01', moveOut: '2026-11-05' })
    expect(toQuery({ ...base, type: 'long' })).toEqual({ type: 'long', moveIn: '2026-11-01', months: '6' })
  })

  it('round-trips through the URL', () => {
    const state = withChanges(EMPTY_SEARCH, { type: 'shared', district: '武侯区', bedrooms: 2, tags: ['独卫'], recommended: true })
    expect(parseSearch(toQuery(state))).toEqual(state)
  })
})

describe('withChanges', () => {
  it('returns a new object and copies tags', () => {
    const next = withChanges(EMPTY_SEARCH, { q: 'x' })
    expect(next).not.toBe(EMPTY_SEARCH)
    expect(next.tags).not.toBe(EMPTY_SEARCH.tags)
  })
})
