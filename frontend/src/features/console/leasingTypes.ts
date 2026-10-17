export type LeaseStatus = 'pending' | 'active' | 'expired' | 'checked_out' | 'void'
export type BillKind = 'rent' | 'deposit' | 'settlement' | 'other'
export type BillStatus = 'unpaid' | 'partial' | 'settled' | 'void'
export type FeeKind = 'fixed' | 'one_time' | 'metered'
/** 收款方式只是登记标签：平台不接任何支付通道 */
export type ManualMethod = 'cash' | 'wechat' | 'alipay' | 'bank' | 'other'
export type PaymentMethod = ManualMethod | 'deposit_offset' | 'deposit_refund'

export const MANUAL_METHODS: readonly ManualMethod[] = ['wechat', 'alipay', 'bank', 'cash', 'other']
export const PAY_CYCLES = [1, 3, 6, 12] as const

export interface Renter {
  id: number
  name: string
  phone: string
  idCardTail: string | null
  note: string
  openLeases?: number
}

export interface RenterInput {
  name: string
  phone: string
  idCardTail: string | null
  note: string
}

export interface FeeItem {
  id: number
  name: string
  kind: FeeKind
  defaultPrice: number
  unit: string
  active: boolean
}

export type FeeItemInput = Omit<FeeItem, 'id'>

export interface LeaseSummary {
  id: number
  leaseNo: string
  listingId: number
  listingTitle: string
  renterId: number
  renterName: string
  renterPhone: string
  startDate: string
  endDate: string
  monthlyRent: number
  deposit: number
  payCycleMonths: number
  status: LeaseStatus
  checkoutDate: string | null
  outstanding: number
  overdue: number
}

export interface LeaseFee {
  feeItemId: number
  name: string
  kind: FeeKind
  price: number
}

export interface BillSummary {
  id: number
  billNo: string
  kind: BillKind
  periodNo: number | null
  periodStart: string | null
  periodEnd: string | null
  dueDate: string
  totalAmount: number
  discountAmount: number
  paidAmount: number
  status: BillStatus
  settledAt: string | null
  note: string
}

export interface MeterReading {
  id: number
  feeItemId: number
  feeName: string
  unit: string
  prevReading: number
  reading: number
  readDate: string
  usage: number
  unitPrice: number
  amount: number
  billId: number | null
  billNo: string | null
}

export interface LeaseDetail extends LeaseSummary {
  advanceDays: number
  occupants: number
  signedDate: string | null
  note: string
  checkoutNote: string
  depositOffset: number
  depositRefund: number
  idCardTail: string | null
  fees: LeaseFee[]
  bills: BillSummary[]
  readings: MeterReading[]
}

export interface SignInput {
  listingId: number
  renterId: number | null
  newRenter: RenterInput | null
  startDate: string
  endDate: string
  monthlyRent: number
  deposit: number
  payCycleMonths: number
  advanceDays: number
  occupants: number
  signedDate: string | null
  fees: { feeItemId: number; price: number | null }[]
  note: string
  inquiryId: number | null
}

export interface PlannedBill {
  kind: BillKind
  periodNo: number | null
  periodStart: string
  periodEnd: string
  dueDate: string
  totalAmount: number
  items: { name: string; quantity: number; unitPrice: number; amount: number }[]
}

export interface BillRow extends BillSummary {
  leaseId: number
  leaseNo: string
  outstanding: number
  renterName: string
  renterPhone: string
  listingTitle: string
  isOverdue: boolean
}

export interface Payment {
  id: number
  amount: number
  method: PaymentMethod
  paidOn: string
  note: string
  status: 'valid' | 'void'
  voidedAt: string | null
  createdAt: string
}

export interface BillDetail extends BillRow {
  items: { id: number; name: string; quantity: number; unitPrice: number; amount: number; meterReadingId: number | null }[]
  payments: Payment[]
}

export interface PaymentRow extends Payment {
  billId: number
  billNo: string
  billKind: BillKind
  leaseId: number
  renterName: string
  listingTitle: string
}

export interface BillsSummary {
  overdueAmount: number
  overdueCount: number
  monthReceivable: number
  monthOutstanding: number
  monthCollected: number
}

export interface CheckoutResult {
  voidedBills: number
  settlementBillId: number | null
  depositOffset: number
  depositRefund: number
  outstanding: number
}
