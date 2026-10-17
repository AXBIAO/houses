import { api } from '@/services/http/apiClient'
import type { Page } from './types'
import type {
  BillDetail, BillRow, BillsSummary, CheckoutResult, FeeItem, FeeItemInput, LeaseDetail, LeaseSummary, ManualMethod,
  PaymentRow, PlannedBill, Renter, RenterInput, SignInput,
} from './leasingTypes'

type Query = Record<string, string | number | boolean | undefined>
const L = '/api/landlord'

export const leasingApi = {
  renters: (q?: string) => api.get<{ items: Renter[] }>(`${L}/renters`, { q }),
  createRenter: (body: RenterInput) => api.post<Renter>(`${L}/renters`, body),
  updateRenter: (id: number, body: RenterInput) => api.put<Renter>(`${L}/renters/${id}`, body),
  deleteRenter: (id: number) => api.delete<void>(`${L}/renters/${id}`),

  feeItems: () => api.get<{ items: FeeItem[] }>(`${L}/fee-items`),
  createFeeItem: (body: FeeItemInput) => api.post<FeeItem>(`${L}/fee-items`, body),
  updateFeeItem: (id: number, body: FeeItemInput) => api.put<FeeItem>(`${L}/fee-items/${id}`, body),
  deleteFeeItem: (id: number) => api.delete<void>(`${L}/fee-items/${id}`),

  leases: (query: Query) => api.get<Page<LeaseSummary>>(`${L}/leases`, query),
  lease: (id: number) => api.get<LeaseDetail>(`${L}/leases/${id}`),
  preview: (body: SignInput) => api.post<{ bills: PlannedBill[]; total: number }>(`${L}/leases/preview`, body),
  sign: (body: SignInput) => api.post<LeaseDetail>(`${L}/leases`, body),
  updateLease: (id: number, body: { occupants: number; signedDate: string | null; note: string }) =>
    api.patch<LeaseDetail>(`${L}/leases/${id}`, body),
  voidLease: (id: number) => api.post<LeaseDetail>(`${L}/leases/${id}/void`),
  checkout: (id: number, body: { checkoutDate: string; extras: { name: string; amount: number }[]; note: string }) =>
    api.post<{ result: CheckoutResult; lease: LeaseDetail }>(`${L}/leases/${id}/checkout`, body),

  lastReading: (leaseId: number, feeItemId: number) =>
    api.get<{ last: { reading: number; readDate: string } | null }>(`${L}/leases/${leaseId}/meter-last`, { feeItemId }),
  addReading: (leaseId: number, body: { feeItemId: number; reading: number; readDate: string; prevReading: number | null }) =>
    api.post<{ id: number; amount: number; billId: number | null }>(`${L}/leases/${leaseId}/meter-readings`, body),
  deleteReading: (id: number) => api.delete<void>(`${L}/meter-readings/${id}`),

  billsSummary: () => api.get<BillsSummary>(`${L}/bills/summary`),
  bills: (query: Query) => api.get<Page<BillRow>>(`${L}/bills`, query),
  bill: (id: number) => api.get<BillDetail>(`${L}/bills/${id}`),
  pay: (id: number, body: { amount: number; method: ManualMethod; paidOn: string | null; note: string }) =>
    api.post<BillDetail>(`${L}/bills/${id}/payments`, body),
  discount: (id: number, body: { amount: number; note: string | null }) => api.put<BillDetail>(`${L}/bills/${id}/discount`, body),
  voidPayment: (id: number) => api.post<{ ok: boolean }>(`${L}/payments/${id}/void`),
  payments: (query: Query) => api.get<Page<PaymentRow>>(`${L}/payments`, query),
}
