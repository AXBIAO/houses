<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BillDialog from '@/components/console/BillDialog.vue'
import LeasingBadge from '@/components/console/LeasingBadge.vue'
import { leasingApi } from '@/features/console/leasingApi'
import type { BillRow, BillsSummary, PaymentRow } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { yuan } from '@/features/console/money'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LandlordBills' })

type View = 'open' | 'overdue' | 'settled' | 'all' | 'payments'
const VIEWS: readonly View[] = ['open', 'overdue', 'settled', 'all', 'payments']
const PAGE_SIZE = 30

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const summary = ref<BillsSummary | null>(null)
const bills = ref<BillRow[]>([])
const payments = ref<PaymentRow[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref(String(route.query.q ?? ''))
const billOpen = ref(false)
const billId = ref<number | null>(null)

const view = computed<View>(() => ((VIEWS as readonly string[]).includes(String(route.query.view)) ? String(route.query.view) as View : 'open'))
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function setQuery(changes: Record<string, string | undefined>) {
  const query = { ...route.query, ...changes }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  void router.replace({ query })
}

async function loadSummary() {
  try {
    summary.value = await leasingApi.billsSummary()
  } catch {
    summary.value = null
  }
}

async function load() {
  loading.value = true
  try {
    if (view.value === 'payments') {
      const res = await leasingApi.payments({ page: page.value, pageSize: PAGE_SIZE })
      payments.value = res.items
      total.value = res.total
    } else {
      const status = view.value === 'open' ? 'open' : view.value === 'settled' ? 'settled' : undefined
      const res = await leasingApi.bills({
        status, overdue: view.value === 'overdue' || undefined, q: String(route.query.q ?? '') || undefined,
        page: page.value, pageSize: PAGE_SIZE,
      })
      bills.value = res.items
      total.value = res.total
    }
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

function openBill(id: number) {
  billId.value = id
  billOpen.value = true
}

async function refresh() {
  await Promise.all([load(), loadSummary()])
}

onMounted(loadSummary)
watch(() => [view.value, page.value, route.query.q], load, { immediate: true })
</script>

<template>
  <div v-if="summary" class="c-stats">
    <button type="button" class="c-stat stat-btn" @click="setQuery({ view: 'overdue', page: undefined })">
      <strong :class="{ 'c-error': summary.overdueCount > 0 }">{{ yuan(summary.overdueAmount) }}</strong>
      <span>{{ t('lease.summary.overdue', { n: summary.overdueCount }) }}</span>
    </button>
    <div class="c-stat"><strong>{{ yuan(summary.monthReceivable) }}</strong><span>{{ t('lease.summary.monthReceivable') }}</span></div>
    <div class="c-stat"><strong>{{ yuan(summary.monthOutstanding) }}</strong><span>{{ t('lease.summary.monthOutstanding') }}</span></div>
    <div class="c-stat"><strong>{{ yuan(summary.monthCollected) }}</strong><span>{{ t('lease.summary.monthCollected') }}</span></div>
  </div>
  <p class="c-hint">{{ t('lease.recordOnly') }}</p>

  <div class="c-toolbar">
    <button
      v-for="v in VIEWS" :key="v" type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': view === v }"
      @click="setQuery({ view: v === 'open' ? undefined : v, page: undefined })"
    >{{ t(`lease.views.${v}`) }}</button>
    <form v-if="view !== 'payments'" class="search" @submit.prevent="setQuery({ q: keyword.trim() || undefined, page: undefined })">
      <input v-model="keyword" class="c-input" type="search" maxlength="40" :placeholder="t('lease.searchBills')" :aria-label="t('lease.searchBills')" />
    </form>
  </div>

  <p v-if="loading && !(view === 'payments' ? payments.length : bills.length)" class="c-hint">{{ t('common.loading') }}</p>
  <template v-else-if="view === 'payments'">
    <div v-if="!payments.length" class="c-empty"><p>{{ t('common.empty') }}</p></div>
    <div v-else class="c-table-wrap">
      <table class="c-table">
        <thead><tr><th>{{ t('lease.paidOn') }}</th><th>{{ t('lease.amount') }}</th><th>{{ t('lease.method') }}</th><th>{{ t('lease.renter') }}</th><th>{{ t('lease.bill') }}</th><th>{{ t('lease.note') }}</th></tr></thead>
        <tbody>
          <tr v-for="p in payments" :key="p.id" :class="{ muted: p.status === 'void' }">
            <td>{{ p.paidOn }}</td>
            <td :class="{ strike: p.status === 'void' }">{{ yuan(p.amount) }}</td>
            <td>{{ t(`lease.methods.${p.method}`) }}<span v-if="p.status === 'void'" class="c-badge" data-tone="muted">{{ t('lease.voided') }}</span></td>
            <td>{{ p.renterName }}<p class="c-hint">{{ p.listingTitle }}</p></td>
            <td><button type="button" class="link" @click="openBill(p.billId)">{{ p.billNo }}</button></td>
            <td class="c-hint">{{ p.note || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
  <template v-else>
    <div v-if="!bills.length" class="c-empty"><p>{{ t('lease.noBills') }}</p></div>
    <div v-else class="c-table-wrap">
      <table class="c-table">
        <thead>
          <tr><th>{{ t('lease.dueDate') }}</th><th>{{ t('lease.renter') }}</th><th>{{ t('lease.billKindCol') }}</th><th>{{ t('lease.total') }}</th><th>{{ t('lease.outstanding') }}</th><th>{{ t('console.col.status') }}</th><th /></tr>
        </thead>
        <tbody>
          <tr v-for="b in bills" :key="b.id" :class="{ muted: b.status === 'void' }">
            <td>{{ b.dueDate }}</td>
            <td>{{ b.renterName }} · {{ b.renterPhone }}<p class="c-hint"><RouterLink :to="`/landlord/leases/${b.leaseId}`" class="link">{{ b.listingTitle }}</RouterLink></p></td>
            <td>{{ b.kind === 'rent' ? t('lease.periodN', { n: b.periodNo }) : t(`lease.billKind.${b.kind}`) }}<p class="c-hint">{{ b.billNo }}</p></td>
            <td>{{ yuan(b.totalAmount) }}</td>
            <td>{{ b.status === 'void' ? '—' : yuan(b.outstanding) }}</td>
            <td><LeasingBadge :bill="b.status" :overdue="b.isOverdue" /></td>
            <td class="c-actions">
              <button type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': b.outstanding > 0 && b.status !== 'void' }" @click="openBill(b.id)">
                {{ b.outstanding > 0 && b.status !== 'void' ? t('lease.recordPayment') : t('lease.view') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>

  <div v-if="pages > 1" class="c-pager">
    <button type="button" class="c-btn c-btn--sm" :disabled="page <= 1" @click="setQuery({ page: String(page - 1) })">{{ t('console.prev') }}</button>
    <span>{{ page }} / {{ pages }}</span>
    <button type="button" class="c-btn c-btn--sm" :disabled="page >= pages" @click="setQuery({ page: String(page + 1) })">{{ t('console.next') }}</button>
  </div>

  <BillDialog v-model="billOpen" :bill-id="billId" @changed="refresh" />
</template>

<style scoped>
.search { flex: 1; min-width: 200px; max-width: 320px; margin-left: auto; }
.stat-btn { text-align: left; cursor: pointer; }
.link { text-decoration: underline; }
.muted td { color: var(--ink-muted); }
.strike { text-decoration: line-through; }
</style>
