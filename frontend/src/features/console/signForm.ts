import type { ConsoleListing } from './types'
import type { FeeItem, SignInput } from './leasingTypes'
import { addDaysIso, addMonthsIso, todayIso } from './money'

export interface SignForm {
  listingId: number
  renterMode: 'existing' | 'new'
  renterId: number
  newRenter: { name: string; phone: string; idCardTail: string; note: string }
  startDate: string
  months: number
  endDate: string
  monthlyRent: number | ''
  deposit: number | ''
  payCycleMonths: number
  advanceDays: number
  occupants: number
  /** feeItemId → 是否选用与改后的价格 */
  fees: Record<number, { on: boolean; price: number | '' }>
  note: string
  inquiryId: number | null
}

export function emptySignForm(fees: FeeItem[], listingId: number, inquiryId: number | null): SignForm {
  const start = todayIso()
  return {
    listingId, renterMode: 'new', renterId: 0, newRenter: { name: '', phone: '', idCardTail: '', note: '' },
    startDate: start, months: 12, endDate: leaseEnd(start, 12), monthlyRent: '', deposit: '', payCycleMonths: 1,
    advanceDays: 0, occupants: 1, note: '', inquiryId,
    fees: Object.fromEntries(fees.filter(f => f.active).map(f => [f.id, { on: false, price: f.defaultPrice }])),
  }
}

/** 租 N 个月：到期日 = 起租日 + N 个月 - 1 天（含当天） */
export function leaseEnd(start: string, months: number): string {
  return addDaysIso(addMonthsIso(start, months), -1)
}

/** 选中房源时带出挂牌月租与押金月数 */
export function defaultsFromListing(listing: ConsoleListing | undefined): Pick<SignForm, 'monthlyRent' | 'deposit'> {
  const rent = listing?.priceMonth ?? ''
  return { monthlyRent: rent, deposit: rent === '' ? '' : rent * (listing?.depositMonths ?? 1) }
}

const PHONE_RE = /^1\d{10}$/

export function toSignInput(form: SignForm): { input: SignInput } | { errorKey: string } {
  if (!form.listingId) return { errorKey: 'lease.errors.listing' }
  if (form.renterMode === 'existing' && !form.renterId) return { errorKey: 'lease.errors.renter' }
  if (form.renterMode === 'new') {
    if (!form.newRenter.name.trim()) return { errorKey: 'lease.errors.renterName' }
    if (!PHONE_RE.test(form.newRenter.phone.trim())) return { errorKey: 'inquiry.phoneInvalid' }
    if (form.newRenter.idCardTail && !/^[0-9Xx]{4}$/.test(form.newRenter.idCardTail.trim())) return { errorKey: 'lease.errors.idTail' }
  }
  if (!form.startDate || !form.endDate || form.endDate < form.startDate) return { errorKey: 'lease.errors.dates' }
  if (form.monthlyRent === '' || Number(form.monthlyRent) < 0) return { errorKey: 'lease.errors.rent' }
  const fees = Object.entries(form.fees).filter(([, v]) => v.on)
    .map(([id, v]) => ({ feeItemId: Number(id), price: v.price === '' ? null : Number(v.price) }))
  return {
    input: {
      listingId: form.listingId,
      renterId: form.renterMode === 'existing' ? form.renterId : null,
      newRenter: form.renterMode === 'new'
        ? { name: form.newRenter.name.trim(), phone: form.newRenter.phone.trim(), idCardTail: form.newRenter.idCardTail.trim() || null, note: form.newRenter.note.trim() }
        : null,
      startDate: form.startDate, endDate: form.endDate, monthlyRent: Number(form.monthlyRent),
      deposit: form.deposit === '' ? 0 : Number(form.deposit), payCycleMonths: form.payCycleMonths,
      advanceDays: form.advanceDays, occupants: form.occupants, signedDate: null, fees, note: form.note.trim(),
      inquiryId: form.inquiryId,
    },
  }
}
