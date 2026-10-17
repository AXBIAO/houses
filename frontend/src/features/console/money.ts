const formatter = new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** 金额统一显示两位小数，负数（退押金）带负号。 */
export function yuan(value: number | null | undefined): string {
  const n = Number(value ?? 0)
  return `${n < 0 ? '-' : ''}¥${formatter.format(Math.abs(n))}`
}

export function todayIso(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

/** 与后端 add_months 一致：按自然月推算，月末对齐。 */
export function addMonthsIso(iso: string, months: number): string {
  const [y, m, d] = iso.split('-').map(Number) as [number, number, number]
  const index = m - 1 + months
  const year = y + Math.floor(index / 12)
  const month = ((index % 12) + 12) % 12
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate()
  return new Date(Date.UTC(year, month, Math.min(d, lastDay))).toISOString().slice(0, 10)
}

export function addDaysIso(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
