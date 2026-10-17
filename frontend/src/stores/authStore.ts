import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, ApiError } from '@/services/http/apiClient'
import { AUTH_TOKEN_KEY, removeAuthToken, setRuntimeAuthToken, readAuthToken } from '@/services/http/authTokenStorage'

export type UserRole = 'user' | 'platform_admin' | 'superadmin'

export interface LandlordMembership {
  id: number
  name: string
  role: 'owner' | 'staff'
  active: boolean
}

export interface AuthUser {
  id: number
  email: string | null
  phone: string | null
  username: string
  role: UserRole
  landlord: LandlordMembership | null
}

interface AuthResponse {
  token: string
  user: AuthUser
}

export interface RegisterInput {
  email?: string | null
  phone?: string | null
  username: string
  password: string
}

function persistToken(token: string): void {
  setRuntimeAuthToken(token)
  try {
    localStorage.setItem(AUTH_TOKEN_KEY, token)
  } catch {
    // 无法持久化时仅保留内存态，本页仍可用
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const initialized = ref(false)
  let initializing: Promise<void> | null = null

  const isLoggedIn = computed(() => user.value !== null)
  const isPlatformAdmin = computed(() => user.value?.role === 'platform_admin' || user.value?.role === 'superadmin')
  const isLandlord = computed(() => user.value?.landlord?.active === true)
  const isSuperAdmin = computed(() => user.value?.role === 'superadmin')
  const isLandlordOwner = computed(() => isLandlord.value && user.value?.landlord?.role === 'owner')

  function applySession(response: AuthResponse): AuthUser {
    persistToken(response.token)
    user.value = response.user
    return response.user
  }

  async function ensureInitialized(): Promise<void> {
    if (initialized.value) return
    initializing ??= (async () => {
      if (!readAuthToken()) return
      try {
        const res = await api.get<{ user: AuthUser }>('/api/auth/me')
        user.value = res.user
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) removeAuthToken()
      }
    })().finally(() => {
      initialized.value = true
    })
    return initializing
  }

  async function login(account: string, password: string): Promise<AuthUser> {
    return applySession(await api.post<AuthResponse>('/api/auth/login', { account, password }))
  }

  async function register(input: RegisterInput): Promise<AuthUser> {
    return applySession(await api.post<AuthResponse>('/api/auth/register', input))
  }

  /** 修改密码后服务端会让旧令牌失效，这里换上新令牌 */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    applySession(await api.post<AuthResponse>('/api/auth/password', { oldPassword, newPassword }))
  }

  /** 平台开通房东或成员变动后刷新身份 */
  async function refresh(): Promise<void> {
    if (!readAuthToken()) return
    const res = await api.get<{ user: AuthUser }>('/api/auth/me')
    user.value = res.user
  }

  function logout(): void {
    removeAuthToken()
    user.value = null
  }

  return { user, initialized, isLoggedIn, isPlatformAdmin, isSuperAdmin, isLandlord, isLandlordOwner, ensureInitialized, login, register, refresh, logout, changePassword }
})
