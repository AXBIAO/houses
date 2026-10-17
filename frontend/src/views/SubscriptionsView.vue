<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Bell, BellOff, BellPlus, Lock, Mail } from 'lucide-vue-next'
import SubscriptionForm from '@/components/subscriptions/SubscriptionForm.vue'
import { subscriptionApi, type AppNotification, type Subscription, type SubscriptionInput } from '@/features/subscriptions/api'
import { describeFilters } from '@/features/subscriptions/describe'
import { errorMessage } from '@/features/console/errors'
import { useAuthDialog } from '@/composables/useAuthDialog'
import { showToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import '@/console.css'

defineOptions({ name: 'SubscriptionsView' })

const FILTER_KEYS = ['type', 'q', 'district', 'minPrice', 'maxPrice', 'bedrooms', 'tags', 'moveIn', 'moveOut', 'months'] as const

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const authDialog = useAuthDialog()
const store = useNotificationStore()

const tab = computed(() => (route.query.tab === 'inbox' ? 'inbox' : 'subs'))
const subs = ref<Subscription[]>([])
const emailAvailable = ref(false)
const inbox = ref<AppNotification[]>([])
const editing = ref<Subscription | 'new' | null>(route.query.new === '1' ? 'new' : null)
const saving = ref(false)
const formError = ref('')
const permission = ref(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)

const initialFilters = computed(() => Object.fromEntries(
  FILTER_KEYS.filter(k => typeof route.query[k] === 'string' && route.query[k]).map(k => [k, String(route.query[k])]),
))

async function loadSubs() {
  try {
    const res = await subscriptionApi.list()
    subs.value = res.items
    emailAvailable.value = res.emailAvailable
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function loadInbox() {
  try {
    const res = await subscriptionApi.notifications({ pageSize: 50 })
    inbox.value = res.items
    store.unread = res.unread
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

function setTab(next: 'subs' | 'inbox') {
  void router.replace({ query: next === 'inbox' ? { tab: 'inbox' } : {} })
}

async function save(input: SubscriptionInput) {
  saving.value = true
  formError.value = ''
  try {
    const target = editing.value
    if (target && target !== 'new') await subscriptionApi.update(target.id, input)
    else await subscriptionApi.create(input)
    showToast(t('subs.saved'))
    editing.value = null
    if (route.query.new) void router.replace({ query: {} })
    await loadSubs()
  } catch (error) {
    formError.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

async function toggle(sub: Subscription, changes: Partial<SubscriptionInput>) {
  try {
    const saved = await subscriptionApi.update(sub.id, { name: sub.name, filters: sub.filters, emailEnabled: sub.emailEnabled, active: sub.active, ...changes })
    subs.value = subs.value.map(s => (s.id === saved.id ? { ...saved, unread: s.unread } : s))
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function remove(sub: Subscription) {
  if (!window.confirm(t('subs.confirmDelete', { name: sub.name }))) return
  try {
    await subscriptionApi.remove(sub.id)
    await loadSubs()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function openNotification(note: AppNotification) {
  if (!note.readAt) {
    void subscriptionApi.markRead([note.id]).then(() => store.refreshUnread())
  }
  await router.push(`/listings/${note.listingId}`)
}

async function readAll() {
  await subscriptionApi.markRead()
  await Promise.all([loadInbox(), store.refreshUnread()])
}

async function askPermission() {
  permission.value = await store.requestBrowserPermission()
}

watch(() => [auth.isLoggedIn, tab.value], ([loggedIn]) => {
  if (!loggedIn) return
  if (tab.value === 'inbox') void loadInbox()
  else void loadSubs()
}, { immediate: true })
// 实时推送到达时刷新收件箱
watch(() => store.lastMessage, () => { if (tab.value === 'inbox') void loadInbox() })
onMounted(() => { void auth.ensureInitialized() })
</script>

<template>
  <div class="subs">
    <header class="subs__head">
      <div>
        <h1>{{ t('navigation.subscriptions') }}</h1>
        <p class="c-hint">{{ t('subs.lead') }}</p>
      </div>
      <nav v-if="auth.isLoggedIn" class="subs__tabs">
        <button type="button" :class="{ 'is-active': tab === 'subs' }" @click="setTab('subs')">{{ t('subs.mine') }}</button>
        <button type="button" :class="{ 'is-active': tab === 'inbox' }" @click="setTab('inbox')">
          {{ t('subs.inbox') }}<span v-if="store.unread" class="subs__count">{{ store.unread }}</span>
        </button>
      </nav>
    </header>

    <section v-if="!auth.isLoggedIn" class="c-empty gate">
      <Lock :size="28" aria-hidden="true" />
      <p>{{ t('subs.loginFirst') }}</p>
      <button type="button" class="c-btn c-btn--primary" @click="authDialog.show()">{{ t('navigation.loginAccount') }}</button>
    </section>

    <template v-else-if="tab === 'subs'">
      <div class="c-toolbar">
        <button v-if="!editing" type="button" class="c-btn c-btn--primary" @click="editing = 'new'"><BellPlus :size="16" aria-hidden="true" />{{ t('subs.create') }}</button>
        <span class="c-toolbar__spacer" />
        <span v-if="permission === 'granted'" class="c-hint"><Bell :size="14" aria-hidden="true" /> {{ t('subs.browserOn') }}</span>
        <button v-else-if="permission === 'default'" type="button" class="c-btn c-btn--sm" @click="askPermission">{{ t('subs.enableBrowser') }}</button>
        <span v-else-if="permission === 'denied'" class="c-hint"><BellOff :size="14" aria-hidden="true" /> {{ t('subs.browserDenied') }}</span>
        <span class="c-hint live">{{ store.connected ? t('subs.liveOn') : t('subs.liveOff') }}</span>
      </div>

      <SubscriptionForm
        v-if="editing" :key="editing === 'new' ? 'new' : editing.id" :initial="editing === 'new' ? null : editing"
        :initial-filters="initialFilters" :email-available="emailAvailable" :saving="saving" :error-text="formError"
        @submit="save" @cancel="editing = null"
      />

      <div v-if="!subs.length && !editing" class="c-empty"><p>{{ t('subs.empty') }}</p></div>
      <ul v-else class="sub-list">
        <li v-for="s in subs" :key="s.id" class="c-card sub" :class="{ 'is-paused': !s.active }">
          <div class="sub__main">
            <h3>{{ s.name }}<span v-if="s.unread" class="subs__count">{{ s.unread }}</span></h3>
            <ul class="sub__chips"><li v-for="label in describeFilters(s.filters, t)" :key="label" class="c-badge">{{ label }}</li></ul>
            <RouterLink :to="{ path: '/listings', query: s.filters }" class="sub__match">{{ t('subs.matchNow', { n: s.matchCount }) }}</RouterLink>
          </div>
          <div class="sub__actions">
            <label class="check"><input type="checkbox" :checked="s.active" @change="toggle(s, { active: ($event.target as HTMLInputElement).checked })" /> {{ t('subs.active') }}</label>
            <label class="check" :title="emailAvailable ? '' : t('subs.emailUnavailable')">
              <input type="checkbox" :checked="s.emailEnabled" :disabled="!emailAvailable" @change="toggle(s, { emailEnabled: ($event.target as HTMLInputElement).checked })" /> <Mail :size="14" aria-hidden="true" /> {{ t('subs.email') }}
            </label>
            <button type="button" class="c-btn c-btn--sm" @click="editing = s">{{ t('console.edit') }}</button>
            <button type="button" class="c-btn c-btn--sm c-btn--danger" @click="remove(s)">{{ t('console.delete') }}</button>
          </div>
        </li>
      </ul>
    </template>

    <template v-else>
      <div class="c-toolbar">
        <span class="c-hint">{{ t('subs.inboxHint') }}</span>
        <span class="c-toolbar__spacer" />
        <button v-if="store.unread" type="button" class="c-btn c-btn--sm" @click="readAll">{{ t('subs.readAll') }}</button>
      </div>
      <div v-if="!inbox.length" class="c-empty"><p>{{ t('subs.inboxEmpty') }}</p></div>
      <ul v-else class="inbox">
        <li v-for="n in inbox" :key="n.id">
          <button type="button" class="note" :class="{ 'is-unread': !n.readAt }" @click="openNotification(n)">
            <span class="note__thumb" :style="n.coverUrl ? { backgroundImage: `url(${JSON.stringify(n.coverUrl)})` } : {}" aria-hidden="true" />
            <span class="note__text">
              <strong>{{ n.title }}</strong>
              <span>{{ n.body }}</span>
              <span class="c-hint">{{ n.subscriptionName ? t('subs.fromSub', { name: n.subscriptionName }) : '' }} · {{ new Date(n.createdAt).toLocaleString() }}</span>
            </span>
            <span v-if="n.kind === 'price_drop'" class="c-badge" data-tone="warn">{{ t('subs.priceDrop') }}</span>
            <span v-else class="c-badge" data-tone="good">{{ t('subs.newListing') }}</span>
          </button>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.subs { display: grid; gap: 18px; }
.subs__head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; }
.subs__head h1 { font-size: clamp(26px, 3vw, 36px); font-weight: 900; font-style: italic; }
.subs__tabs { display: flex; gap: 4px; padding: 4px; border: 1.5px solid var(--rule-strong); border-radius: 12px; background: var(--paper-raised); }
.subs__tabs button { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 8px; color: var(--ink-secondary); font-weight: 800; }
.subs__tabs button.is-active { background: var(--ink); color: var(--paper-raised); }
.subs__count { display: inline-grid; place-items: center; min-width: 18px; height: 18px; margin-left: 6px; padding: 0 5px; border-radius: 999px; background: var(--danger, #d64c3b); color: #fff; font-size: 11px; font-weight: 800; }
.gate { display: grid; justify-items: center; gap: 12px; }
.live { margin-left: 8px; }
.sub-list { display: grid; gap: 12px; }
.sub { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; box-shadow: none; }
.sub.is-paused { opacity: .6; }
.sub__main { display: grid; flex: 1; min-width: 240px; gap: 8px; }
.sub__main h3 { display: flex; align-items: center; font-size: 17px; font-weight: 900; }
.sub__chips { display: flex; flex-wrap: wrap; gap: 6px; }
.sub__match { width: fit-content; color: var(--ink-secondary); font-size: 13px; font-weight: 700; text-decoration: underline; }
.sub__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.check { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700; }
.inbox { display: grid; gap: 8px; }
.note { display: flex; align-items: center; gap: 12px; width: 100%; padding: 12px; border: 1.5px solid var(--rule); border-radius: 12px; background: var(--paper-raised); color: inherit; text-align: left; cursor: pointer; }
.note:hover { border-color: var(--rule-strong); }
.note.is-unread { border-color: var(--rule-strong); box-shadow: inset 4px 0 0 var(--acid-strong); }
.note__thumb { flex: none; width: 64px; height: 48px; border-radius: 8px; background: var(--acid-soft) center / cover no-repeat; }
.note__text { display: grid; flex: 1; gap: 2px; min-width: 0; }
.note__text strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
