import { describe, expect, it } from 'vitest'
import { subscribableFilters, withoutCondition } from './aiFilters'

const base = { type: 'short', district: '高新区', maxPrice: '300', tags: '近地铁,江景', moveIn: '2026-11-01', moveOut: '2026-11-03' }

describe('withoutCondition', () => {
  it('removes one tag and keeps the others', () => {
    expect(withoutCondition(base, 'tag:江景').tags).toBe('近地铁')
    expect(withoutCondition({ tags: '近地铁' }, 'tag:近地铁')).toEqual({})
  })

  it('removes all params behind a chip', () => {
    expect(withoutCondition(base, 'moveIn')).not.toHaveProperty('moveOut')
    expect(withoutCondition({ minPrice: '1', maxPrice: '2' }, 'price')).toEqual({})
    expect(withoutCondition({ lat: '1', lng: '2', radiusKm: '5', sort: 'distance', bedrooms: '2' }, 'near')).toEqual({ bedrooms: '2' })
  })

  it('does not mutate the input', () => {
    withoutCondition(base, 'district')
    expect(base.district).toBe('高新区')
  })
})

describe('subscribableFilters', () => {
  it('drops location-only params', () => {
    expect(subscribableFilters({ district: 'x', lat: '1', lng: '2', radiusKm: '5', sort: 'distance' })).toEqual({ district: 'x' })
  })
})
