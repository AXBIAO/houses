import { ref } from 'vue'
import { defineStore } from 'pinia'
import { subscriptionApi } from '@/features/subscriptions/api'
import { readAuthToken } from '@/services/http/authTokenStorage'
import { showToast } from '@/composables/useToast'

export interface PushMessage {
  id: number
  kind: 'new' | 'price_drop'
  title: string
  body: string
  listingId: number
  subscriptionName: string
}

const POLL_MS = 60_000
const MAX_BACKOFF_MS = 60_000

/**
 * 订阅通知：登录后通过 SSE 实时接收（fetch 读取流，可以带 Authorization 头）；
 * 连接断开时指数退避重连，另有每分钟一次的未读数轮询兜底。
 */
export const useNotificationStore = defineStore('notifications', () => {
  const unread = ref(0)
  const connected = ref(false)
  const lastMessage = ref<PushMessage | null>(null)
  let controller: AbortController | null = null
  let pollTimer: number | undefined
  let retryTimer: number | undefined
  let backoff = 2_000

  async function refreshUnread() {
    try {
      unread.value = (await subscriptionApi.notifications({ unread: true, pageSize: 1 })).unread
    } catch {
      // 登录失效等情况由下一次请求处理
    }
  }

  function notifyBrowser(message: PushMessage) {
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted' || !document.hidden) return
    const n = new Notification(message.title, { body: message.body, tag: `houses-${message.id}`, icon: '/favicon.svg' })
    n.onclick = () => {
      window.focus()
      window.location.href = `/listings/${message.listingId}`
    }
  }

  function handle(message: PushMessage) {
    unread.value += 1
    lastMessage.value = message
    showToast(`${message.title} · ${message.body}`)
    notifyBrowser(message)
  }

  async function readStream(signal: AbortSignal) {
    const token = readAuthToken()
    if (!token) return
    const res = await fetch('/api/notifications/stream', { headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }, signal })
    if (!res.ok || !res.body) throw new Error(`stream ${res.status}`)
    connected.value = true
    backoff = 2_000
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value
      let index: number
      while ((index = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, index)
        buffer = buffer.slice(index + 2)
        const event = /^event: (.+)$/m.exec(block)?.[1]
        const data = /^data: (.+)$/m.exec(block)?.[1]
        if (event === 'notification' && data) {
          try {
            handle(JSON.parse(data) as PushMessage)
          } catch {
            // 忽略格式不对的消息
          }
        }
      }
    }
  }

  function scheduleReconnect() {
    window.clearTimeout(retryTimer)
    retryTimer = window.setTimeout(connect, backoff)
    backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
  }

  function connect() {
    disconnect(false)
    if (!readAuthToken()) return
    const current = new AbortController()
    controller = current
    void readStream(current.signal)
      .catch(() => undefined)
      .finally(() => {
        connected.value = false
        if (controller === current && !current.signal.aborted) scheduleReconnect()
      })
    void refreshUnread()
    window.clearInterval(pollTimer)
    pollTimer = window.setInterval(refreshUnread, POLL_MS)
  }

  function disconnect(resetCount = true) {
    controller?.abort()
    controller = null
    window.clearTimeout(retryTimer)
    window.clearInterval(pollTimer)
    connected.value = false
    if (resetCount) unread.value = 0
  }

  async function requestBrowserPermission(): Promise<NotificationPermission | 'unsupported'> {
    if (typeof Notification === 'undefined') return 'unsupported'
    return Notification.permission === 'default' ? Notification.requestPermission() : Notification.permission
  }

  return { unread, connected, lastMessage, connect, disconnect, refreshUnread, requestBrowserPermission }
})
