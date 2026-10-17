import { api } from '@/services/http/apiClient'
import type {
  AdminLandlord, Block, ConsoleListing, ConsoleListingDetail, Estate, EstateInput, Inquiry, InquiryStatus,
  ListingImage, ListingInput, ListingStatus, Member, Overview, Page,
} from './types'

type Query = Record<string, string | number | undefined>

const L = '/api/landlord'

export const landlordApi = {
  overview: () => api.get<Overview>(`${L}/overview`),

  estates: () => api.get<{ items: Estate[] }>(`${L}/estates`),
  createEstate: (body: EstateInput) => api.post<Estate>(`${L}/estates`, body),
  updateEstate: (id: number, body: EstateInput) => api.put<Estate>(`${L}/estates/${id}`, body),
  deleteEstate: (id: number) => api.delete<void>(`${L}/estates/${id}`),

  listings: (query: Query) => api.get<Page<ConsoleListing>>(`${L}/listings`, query),
  listing: (id: number) => api.get<ConsoleListingDetail>(`${L}/listings/${id}`),
  createListing: (body: ListingInput) => api.post<ConsoleListingDetail>(`${L}/listings`, body),
  updateListing: (id: number, body: ListingInput) => api.put<ConsoleListingDetail>(`${L}/listings/${id}`, body),
  setStatus: (id: number, status: Exclude<ListingStatus, 'draft'>) =>
    api.post<ConsoleListingDetail>(`${L}/listings/${id}/status`, { status }),
  deleteListing: (id: number) => api.delete<void>(`${L}/listings/${id}`),

  uploadImage: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<ListingImage>(`${L}/listings/${id}/images`, form)
  },
  reorderImages: (id: number, imageIds: number[]) => api.put<ConsoleListingDetail>(`${L}/listings/${id}/images/order`, { imageIds }),
  deleteImage: (id: number, imageId: number) => api.delete<void>(`${L}/listings/${id}/images/${imageId}`),

  addBlock: (id: number, body: { start: string; end: string; note: string }) => api.post<Block>(`${L}/listings/${id}/blocks`, body),
  deleteBlock: (id: number, blockId: number) => api.delete<void>(`${L}/listings/${id}/blocks/${blockId}`),

  inquiries: (query: Query) => api.get<Page<Inquiry>>(`${L}/inquiries`, query),
  updateInquiry: (id: number, body: { status: InquiryStatus; note?: string }) => api.patch<Inquiry>(`${L}/inquiries/${id}`, body),

  members: () => api.get<{ items: Member[] }>(`${L}/members`),
  addMember: (account: string, role: Member['role']) => api.post<unknown>(`${L}/members`, { account, role }),
  removeMember: (userId: number) => api.delete<void>(`${L}/members/${userId}`),
}

export interface LandlordCreateInput {
  name: string
  contactName: string | null
  contactPhone: string | null
  ownerAccount: string
}

export const adminApi = {
  landlords: (query: Query) => api.get<Page<AdminLandlord>>('/api/admin/landlords', query),
  createLandlord: (body: LandlordCreateInput) => api.post<AdminLandlord>('/api/admin/landlords', body),
  updateLandlord: (id: number, body: Partial<Pick<AdminLandlord, 'name' | 'contactName' | 'contactPhone' | 'status'>>) =>
    api.patch<AdminLandlord>(`/api/admin/landlords/${id}`, body),
  listings: (query: Query) => api.get<Page<ConsoleListing>>('/api/admin/listings', query),
  moderate: (id: number, body: { status?: 'offline'; recommended?: boolean }) => api.patch<{ ok: boolean }>(`/api/admin/listings/${id}`, body),
}

export interface LlmSettings {
  source: 'db' | 'env' | 'none'
  enabled: boolean
  baseUrl: string
  model: string
  timeout: number
  apiKeySet: boolean
  apiKeyTail: string | null
}

export interface SmtpSettings {
  source: 'db' | 'env' | 'none'
  enabled: boolean
  host: string
  port: number
  user: string
  sender: string
  useTls: boolean
  passwordSet: boolean
  passwordTail: string | null
}

export interface ProbeResult {
  ok: boolean
  message: string
  filters?: Record<string, unknown>
  raw?: string
}

export const settingsApi = {
  get: () => api.get<{ llm: LlmSettings; smtp: SmtpSettings }>('/api/admin/settings'),
  /** apiKey：undefined/null = 保持不变，'' = 清空 */
  saveLlm: (body: { baseUrl: string; model: string; timeout: number; apiKey: string | null }) => api.put<LlmSettings>('/api/admin/settings/llm', body),
  saveSmtp: (body: { host: string; port: number; user: string; sender: string; useTls: boolean; password: string | null }) =>
    api.put<SmtpSettings>('/api/admin/settings/smtp', body),
  reset: (key: 'llm' | 'smtp') => api.delete<{ llm: LlmSettings; smtp: SmtpSettings }>(`/api/admin/settings/${key}`),
  testLlm: (query?: string) => api.post<ProbeResult>('/api/admin/settings/llm/test', query ? { query } : {}),
  testSmtp: (to: string) => api.post<ProbeResult>('/api/admin/settings/smtp/test', { to }),
}
