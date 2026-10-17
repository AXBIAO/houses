<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import LeasingBadge from '@/components/console/LeasingBadge.vue'
import { leasingApi } from '@/features/console/leasingApi'
import type { LeaseStatus, LeaseSummary } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { yuan } from '@/features/console/money'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LandlordLeases' })

const PAGE_SIZE = 20
const STATUSES: readonly LeaseStatus[] = ['active', 'pending', 'expired', 'checked_out', 'void']

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const items = ref<LeaseSummary[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref(String(route.query.q ?? ''))

const status = computed(() => (STATUSES as readonly string[]).includes(String(route.query.status)) ? String(route.query.status) : undefined)
const expiring = computed(() => route.query.expiring === 'true')
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function setQuery(changes: Record<string, string | undefined>) {
  const query = { ...route.query, ...changes }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  void router.replace({ query })
}

async function load() {
  loading.value = true
  try {
    const res = await leasingApi.leases({ status: status.value, expiring: expiring.value || undefined, q: String(route.query.q ?? '') || undefined, page: page.value, pageSize: PAGE_SIZE })
    items.value = res.items
    total.value = res.total
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

watch(() => [status.value, expiring.value, page.value, route.query.q], load, { immediate: true })
</script>

<template>
  <div class="c-toolbar">
    <select class="c-select narrow" :value="status ?? ''" :aria-label="t('console.statusFilter')" @change="setQuery({ status: ($event.target as HTMLSelectElement).value || undefined, page: undefined })">
      <option value="">{{ t('rentType.all') }}</option>
      <option v-for="s in STATUSES" :key="s" :value="s">{{ t(`lease.status.${s}`) }}</option>
    </select>
    <button type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': expiring }" @click="setQuery({ expiring: expiring ? undefined : 'true', page: undefined })">{{ t('lease.expiringSoon') }}</button>
    <form class="search" @submit.prevent="setQuery({ q: keyword.trim() || undefined, page: undefined })">
      <input v-model="keyword" class="c-input" type="search" maxlength="40" :placeholder="t('lease.searchLeases')" :aria-label="t('lease.searchLeases')" />
    </form>
    <span class="c-toolbar__spacer" />
    <RouterLink to="/landlord/leases/new" class="c-btn c-btn--primary"><Plus :size="16" aria-hidden="true" />{{ t('lease.sign') }}</RouterLink>
  </div>

  <p v-if="loading && !items.length" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!items.length" class="c-empty"><p>{{ t('lease.noLeases') }}</p></div>
  <div v-else class="c-table-wrap">
    <table class="c-table">
      <thead>
        <tr>
          <th>{{ t('lease.leaseNo') }}</th><th>{{ t('console.col.listing') }}</th><th>{{ t('lease.renter') }}</th>
          <th>{{ t('lease.term') }}</th><th>{{ t('lease.monthlyRent') }}</th><th>{{ t('console.col.status') }}</th><th>{{ t('lease.outstanding') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in items" :key="l.id">
          <td><RouterLink :to="`/landlord/leases/${l.id}`" class="link">{{ l.leaseNo }}</RouterLink></td>
          <td>{{ l.listingTitle }}</td>
          <td>{{ l.renterName }}<p class="c-hint">{{ l.renterPhone }}</p></td>
          <td>{{ l.startDate }} ~ {{ l.endDate }}<p class="c-hint">{{ t('lease.cycleN', { n: l.payCycleMonths }) }}</p></td>
          <td>{{ yuan(l.monthlyRent) }}</td>
          <td><LeasingBadge :lease="l.status" /></td>
          <td>
            <span :class="{ 'c-error': l.overdue > 0 }">{{ yuan(l.outstanding) }}</span>
            <p v-if="l.overdue > 0" class="c-hint">{{ t('lease.overdueAmount', { amount: yuan(l.overdue) }) }}</p>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div v-if="pages > 1" class="c-pager">
    <button type="button" class="c-btn c-btn--sm" :disabled="page <= 1" @click="setQuery({ page: String(page - 1) })">{{ t('console.prev') }}</button>
    <span>{{ page }} / {{ pages }}</span>
    <button type="button" class="c-btn c-btn--sm" :disabled="page >= pages" @click="setQuery({ page: String(page + 1) })">{{ t('console.next') }}</button>
  </div>
</template>

<style scoped>
.narrow { width: auto; }
.search { flex: 1; min-width: 200px; max-width: 320px; }
.link { font-weight: 800; text-decoration: underline; }
</style>
