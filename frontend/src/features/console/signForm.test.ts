import { describe, expect, it } from 'vitest'
import { emptySignForm, leaseEnd, toSignInput, type SignForm } from './signForm'
import type { FeeItem } from './leasingTypes'

const FEES: FeeItem[] = [
  { id: 1, name: '管理费', kind: 'fixed', defaultPrice: 50, unit: '', active: true },
  { id: 2, name: '电费', kind: 'metered', defaultPrice: 1.2, unit: '度', active: true },
  { id: 3, name: '旧项目', kind: 'fixed', defaultPrice: 9, unit: '', active: false },
]

const filled = (changes: Partial<SignForm> = {}): SignForm => ({
  ...emptySignForm(FEES, 7, null),
  newRenter: { name: ' 张三 ', phone: '13600000000', idCardTail: '', note: '' },
  monthlyRent: 3000,
  deposit: 3000,
  ...changes,
})

describe('leaseEnd', () => {
  it('ends the day before the same date N months later', () => {
    expect(leaseEnd('2026-11-01', 12)).toBe('2027-10-31')
    expect(leaseEnd('2027-01-31', 1)).toBe('2027-02-27')
  })
})

describe('toSignInput', () => {
  it('skips inactive fee items and sends only selected fees', () => {
    const form = filled()
    expect(Object.keys(form.fees)).toEqual(['1', '2'])
    form.fees[2] = { on: true, price: 1.5 }
    const result = toSignInput(form)
    expect(result).toMatchObject({ input: { listingId: 7, renterId: null, fees: [{ feeItemId: 2, price: 1.5 }] } })
    expect('input' in result && result.input.newRenter?.name).toBe('张三')
  })

  it('validates renter, dates and rent', () => {
    expect(toSignInput(filled({ renterMode: 'existing' }))).toEqual({ errorKey: 'lease.errors.renter' })
    expect(toSignInput(filled({ newRenter: { name: '李四', phone: '123', idCardTail: '', note: '' } }))).toEqual({ errorKey: 'inquiry.phoneInvalid' })
    expect(toSignInput(filled({ newRenter: { name: '李四', phone: '13600000000', idCardTail: '510104199001011234', note: '' } }))).toEqual({ errorKey: 'lease.errors.idTail' })
    expect(toSignInput(filled({ endDate: '2000-01-01' }))).toEqual({ errorKey: 'lease.errors.dates' })
    expect(toSignInput(filled({ monthlyRent: '' }))).toEqual({ errorKey: 'lease.errors.rent' })
  })
})
