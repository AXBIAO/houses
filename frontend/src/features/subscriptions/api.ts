import { api } from '@/services/http/apiClient'
import type { ListingSummary } from '@/features/listings/types'

export interface AiCondition {
  key: string
  label: string
}

export interface AiResult {
  query: string
  source: 'llm' | 'rules'
  llmEnabled: boolean
  understood: boolean
  needLocation: boolean
  conditions: AiCondition[]
  filters: Record<string, string>
  relaxed: string[]
  total: number
  items: (ListingSummary & { reasons: string[] })[]
}

export interface Subscription {
  id: number
  name: string
  filters: Record<string, string>
  emailEnabled: boolean
  active: boolean
  unread: number
  matchCount: number
  createdAt: string
}

export interface SubscriptionInput {
  name: string
  filters: Record<string, string>
  emailEnabled: boolean
  active: boolean
}

export interface AppNotification {
  id: number
  subscriptionId: number | null
  subscriptionName: string | null
  listingId: number
  kind: 'new' | 'price_drop'
  price: number
  title: string
  body: string
  readAt: string | null
  createdAt: string
  coverUrl: string | null
}

export const aiApi = {
  search: (query: string, position?: { lat: number; lng: number } | null) =>
    api.post<AiResult>('/api/ai/search', { query, lat: position?.lat ?? null, lng: position?.lng ?? null }),
}

export const subscriptionApi = {
  list: () => api.get<{ items: Subscription[]; emailAvailable: boolean }>('/api/subscriptions'),
  create: (body: SubscriptionInput) => api.post<Subscription>('/api/subscriptions', body),
  update: (id: number, body: SubscriptionInput) => api.put<Subscription>(`/api/subscriptions/${id}`, body),
  remove: (id: number) => api.delete<void>(`/api/subscriptions/${id}`),
  notifications: (query: { unread?: boolean; page?: number; pageSize?: number }) =>
    api.get<{ items: AppNotification[]; total: number; unread: number }>('/api/notifications', query),
  markRead: (ids?: number[]) => api.post<{ updated: number }>('/api/notifications/read', ids ? { ids } : {}),
}
