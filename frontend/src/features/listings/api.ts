import { api } from '@/services/http/apiClient'
import type { Facets, HomeFeed, ListingDetail, ListingPage, ListingSummary } from './types'

type Params = Record<string, string | number | undefined>

export interface MapResult {
  items: ListingSummary[]
  total: number
  truncated: boolean
}

export interface InquiryInput {
  name: string
  phone: string
  message: string
  moveIn?: string | null
  moveOut?: string | null
}

export const listingsApi = {
  search: (params: Params, signal?: AbortSignal) => api.get<ListingPage>('/api/listings', params, signal),
  map: (params: Params, signal?: AbortSignal) => api.get<MapResult>('/api/listings/map', params, signal),
  home: () => api.get<HomeFeed>('/api/listings/home'),
  facets: () => api.get<Facets>('/api/listings/facets'),
  detail: (id: number) => api.get<ListingDetail>(`/api/listings/${id}`),
  inquire: (id: number, body: InquiryInput) => api.post<{ id: number }>(`/api/listings/${id}/inquiries`, body),
}
