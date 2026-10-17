import { ApiError } from '@/services/http/apiClient'

/** 4xx 的业务提示直接展示（后端已给出中文原因）；网络错误和 5xx 用通用文案。 */
export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError && error.status >= 400 && error.status < 500 ? error.message : fallback
}
