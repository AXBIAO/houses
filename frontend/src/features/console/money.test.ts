import { describe, expect, it } from 'vitest'
import { addDaysIso, addMonthsIso, yuan } from './money'

describe('addMonthsIso', () => {
  it('clamps to month end like the backend planner', () => {
    expect(addMonthsIso('2027-01-31', 1)).toBe('2027-02-28')
    expect(addMonthsIso('2028-01-31', 1)).toBe('2028-02-29')
    expect(addMonthsIso('2026-11-15', 12)).toBe('2027-11-15')
    expect(addMonthsIso('2026-03-31', -1)).toBe('2026-02-28')
  })
})

describe('addDaysIso', () => {
  it('crosses month and year boundaries', () => {
    expect(addDaysIso('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDaysIso('2027-03-01', -1)).toBe('2027-02-28')
  })
})

describe('yuan', () => {
  it('formats with two decimals and a sign for refunds', () => {
    expect(yuan(3000)).toBe('¥3,000.00')
    expect(yuan(-1790.5)).toBe('-¥1,790.50')
    expect(yuan(null)).toBe('¥0.00')
  })
})
