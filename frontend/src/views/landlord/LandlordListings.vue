<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import ListingStatusBadge from '@/components/console/ListingStatusBadge.vue'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { ConsoleListing, ListingStatus } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LandlordListings' })

const PAGE_SIZE = 20
const STATUSES: readonly ListingStatus[] = ['published', 'draft', 'offline']

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const items = ref<ConsoleListing[]>([])
const total = ref(0)
const loading = ref(false)
const busyId = ref<number | null>(null)
const errorText = ref('')
const keyword = ref(String(route.query.q ?? ''))

const status = computed(() => (STATUSES as readonly string[]).includes(String(route.query.status)) ? String(route.query.status) as ListingStatus : null)
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function setQuery(changes: Record<string, string | undefined>) {
  const query = { ...route.query, ...changes }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  void router.replace({ query })
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const res = await landlordApi.listings({ status: status.value ?? undefined, q: String(route.query.q ?? '') || undefined, page: page.value, pageSize: PAGE_SIZE })
    items.value = res.items
    total.value = res.total
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    loading.value = false
  }
}

async function run(listing: ConsoleListing, action: () => Promise<unknown>, doneKey: string) {
  busyId.value = listing.id
  try {
    await action()
    showToast(t(doneKey))
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    busyId.value = null
  }
}

const publish = (l: ConsoleListing) => run(l, () => landlordApi.setStatus(l.id, 'published'), 'console.published')
const takeDown = (l: ConsoleListing) => run(l, () => landlordApi.setStatus(l.id, 'offline'), 'console.offlined')
function remove(l: ConsoleListing) {
  if (!window.confirm(t('console.confirmDelete', { title: l.title }))) return
  void run(l, () => landlordApi.deleteListing(l.id), 'console.deleted')
}
const price = (l: ConsoleListing) => (l.rentType === 'short' ? `¥${l.priceNight}${t('common.perNight')}` : `¥${l.priceMonth}${t('common.perMonth')}`)

watch(() => [status.value, page.value, route.query.q], load, { immediate: true })
</script>

<template>
  <div class="c-toolbar">
    <select class="c-select toolbar-select" :value="status ?? ''" :aria-label="t('console.statusFilter')" @change="setQuery({ status: ($event.target as HTMLSelectElement).value || undefined, page: undefined })">
      <option value="">{{ t('rentType.all') }}</option>
      <option v-for="s in STATUSES" :key="s" :value="s">{{ t(`console.status.${s}`) }}</option>
    </select>
    <form class="toolbar-search" @submit.prevent="setQuery({ q: keyword.trim() || undefined, page: undefined })">
      <input v-model="keyword" class="c-input" type="search" maxlength="60" :placeholder="t('console.searchListings')" :aria-label="t('console.searchListings')" />
    </form>
    <span class="c-toolbar__spacer" />
    <RouterLink to="/landlord/listings/new" class="c-btn c-btn--primary"><Plus :size="16" aria-hidden="true" />{{ t('console.newListing') }}</RouterLink>
  </div>

  <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
  <p v-else-if="loading && !items.length" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!items.length" class="c-empty">
    <p>{{ t('console.noListings') }}</p>
  </div>
  <div v-else class="c-table-wrap">
    <table class="c-table">
      <thead>
        <tr>
          <th>{{ t('console.col.listing') }}</th><th>{{ t('console.col.type') }}</th><th>{{ t('console.col.price') }}</th>
          <th>{{ t('console.col.status') }}</th><th>{{ t('console.col.inquiries') }}</th><th />
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in items" :key="l.id">
          <td>
            <div class="cell-listing">
              <span class="c-thumb" :style="l.coverUrl ? { backgroundImage: `url(${JSON.stringify(l.coverUrl)})` } : {}" aria-hidden="true" />
              <div>
                <RouterLink :to="`/landlord/listings/${l.id}`" class="cell-title">{{ l.title }}</RouterLink>
                <p class="c-hint">{{ l.estateName }} · {{ l.district }}</p>
              </div>
            </div>
          </td>
          <td>{{ t(`rentType.${l.rentType}`) }}</td>
          <td>{{ price(l) }}</td>
          <td><ListingStatusBadge :status="l.status" /></td>
          <td>{{ l.newInquiries ? t('console.newCount', { n: l.newInquiries }) : '—' }}</td>
          <td class="c-actions">
            <RouterLink :to="`/landlord/listings/${l.id}`" class="c-btn c-btn--sm">{{ t('console.edit') }}</RouterLink>
            <button v-if="l.status !== 'published'" type="button" class="c-btn c-btn--sm c-btn--primary" :disabled="busyId === l.id" @click="publish(l)">{{ t('console.publish') }}</button>
            <button v-else type="button" class="c-btn c-btn--sm" :disabled="busyId === l.id" @click="takeDown(l)">{{ t('console.offline') }}</button>
            <button v-if="l.status !== 'published'" type="button" class="c-btn c-btn--sm c-btn--danger" :disabled="busyId === l.id" @click="remove(l)">{{ t('console.delete') }}</button>
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
.toolbar-select { width: auto; }
.toolbar-search { flex: 1; min-width: 200px; max-width: 360px; }
.cell-listing { display: flex; align-items: center; gap: 10px; min-width: 240px; }
.cell-title { font-weight: 800; }
.cell-title:hover { text-decoration: underline; }
</style>
