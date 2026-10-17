<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ListingStatusBadge from '@/components/console/ListingStatusBadge.vue'
import { adminApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { ConsoleListing, ListingStatus } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'AdminListings' })

const PAGE_SIZE = 30
const STATUSES: readonly ListingStatus[] = ['published', 'draft', 'offline']

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const items = ref<ConsoleListing[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref(String(route.query.q ?? ''))

const landlordId = computed(() => Number(route.query.landlordId) || undefined)
const status = computed(() => (STATUSES as readonly string[]).includes(String(route.query.status)) ? String(route.query.status) as ListingStatus : undefined)
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
    const res = await adminApi.listings({ landlordId: landlordId.value, status: status.value, q: String(route.query.q ?? '') || undefined, page: page.value, pageSize: PAGE_SIZE })
    items.value = res.items
    total.value = res.total
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

async function moderate(listing: ConsoleListing, body: { status?: 'offline'; recommended?: boolean }) {
  if (body.status === 'offline' && !window.confirm(t('console.confirmForceOffline', { title: listing.title }))) return
  try {
    await adminApi.moderate(listing.id, body)
    showToast(t('console.saved'))
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

watch(() => [landlordId.value, status.value, page.value, route.query.q], load, { immediate: true })
</script>

<template>
  <div class="c-toolbar">
    <select class="c-select narrow" :value="status ?? ''" :aria-label="t('console.statusFilter')" @change="setQuery({ status: ($event.target as HTMLSelectElement).value || undefined, page: undefined })">
      <option value="">{{ t('rentType.all') }}</option>
      <option v-for="s in STATUSES" :key="s" :value="s">{{ t(`console.status.${s}`) }}</option>
    </select>
    <form class="search" @submit.prevent="setQuery({ q: keyword.trim() || undefined, page: undefined })">
      <input v-model="keyword" class="c-input" type="search" maxlength="60" :placeholder="t('console.searchListings')" :aria-label="t('console.searchListings')" />
    </form>
    <button v-if="landlordId" type="button" class="c-btn c-btn--sm" @click="setQuery({ landlordId: undefined, page: undefined })">
      {{ t('console.clearLandlordFilter', { id: landlordId }) }} ×
    </button>
  </div>

  <p v-if="loading && !items.length" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!items.length" class="c-empty"><p>{{ t('common.empty') }}</p></div>
  <div v-else class="c-table-wrap">
    <table class="c-table">
      <thead>
        <tr>
          <th>{{ t('console.col.listing') }}</th><th>{{ t('console.col.landlord') }}</th><th>{{ t('console.col.type') }}</th>
          <th>{{ t('console.col.status') }}</th><th>{{ t('home.recommended') }}</th><th />
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in items" :key="l.id">
          <td>
            <a v-if="l.status === 'published'" :href="`/listings/${l.id}`" target="_blank" rel="noopener" class="title">{{ l.title }}</a>
            <span v-else class="title">{{ l.title }}</span>
            <p class="c-hint">{{ l.estateName }} · {{ l.district }}</p>
          </td>
          <td>{{ l.landlordName }}</td>
          <td>{{ t(`rentType.${l.rentType}`) }}</td>
          <td><ListingStatusBadge :status="l.status" /></td>
          <td>
            <label class="recommend">
              <input type="checkbox" :checked="l.recommended" @change="moderate(l, { recommended: ($event.target as HTMLInputElement).checked })" />
              <span class="sr-only">{{ t('home.recommended') }}</span>
            </label>
          </td>
          <td class="c-actions">
            <button v-if="l.status === 'published'" type="button" class="c-btn c-btn--sm c-btn--danger" @click="moderate(l, { status: 'offline' })">{{ t('console.forceOffline') }}</button>
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
.search { flex: 1; min-width: 200px; max-width: 360px; }
.title { font-weight: 800; }
a.title:hover { text-decoration: underline; }
.recommend input { width: 18px; height: 18px; accent-color: var(--acid-strong); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
