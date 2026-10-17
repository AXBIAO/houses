<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { BellPlus, Map as MapIcon } from 'lucide-vue-next'
import ListingCard from '@/components/listing/ListingCard.vue'
import ListingFilterBar from '@/components/listing/ListingFilterBar.vue'
import ListingGridSkeleton from '@/components/listing/ListingGridSkeleton.vue'
import { listingsApi } from '@/features/listings/api'
import { parseSearch, toQuery, type SearchState } from '@/features/listings/searchQuery'
import { useFacets } from '@/features/listings/useFacets'
import type { ListingSummary } from '@/features/listings/types'
import { ApiError } from '@/services/http/apiClient'

defineOptions({ name: 'ListingsView' })

const PAGE_SIZE = 20

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const facets = useFacets()

const search = computed(() => parseSearch(route.query))
const items = ref<ListingSummary[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const errorText = ref('')
let controller: AbortController | null = null

const hasMore = computed(() => items.value.length < total.value)

function applySearch(next: SearchState) {
  void router.replace({ query: toQuery(next) })
}

async function fetchPage(nextPage: number) {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  errorText.value = ''
  try {
    const res = await listingsApi.search({ ...toQuery(search.value), page: nextPage, pageSize: PAGE_SIZE }, current.signal)
    items.value = nextPage === 1 ? res.items : [...items.value, ...res.items]
    total.value = res.total
    page.value = nextPage
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    errorText.value = error instanceof ApiError && error.status === 422 ? error.message : t('common.error')
    if (nextPage === 1) items.value = []
  } finally {
    if (controller === current) loading.value = false
  }
}

// 离开本页时全局 route 会先变，忽略不属于本页的查询变化
watch(() => JSON.stringify(toQuery(search.value)), () => {
  if (route.name === 'listings') void fetchPage(1)
}, { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="listings">
    <header class="listings__head">
      <h1>{{ t('navigation.listings') }}</h1>
      <div class="listings__links">
        <RouterLink :to="{ path: '/subscriptions', query: { new: '1', ...route.query } }" class="listings__map"><BellPlus :size="16" aria-hidden="true" />{{ t('subs.subscribeThis') }}</RouterLink>
        <RouterLink :to="{ path: '/map', query: route.query }" class="listings__map"><MapIcon :size="16" aria-hidden="true" />{{ t('navigation.map') }}</RouterLink>
      </div>
    </header>

    <ListingFilterBar :model-value="search" :facets="facets" @update:model-value="applySearch" />

    <p class="listings__count" aria-live="polite">
      <template v-if="!loading || items.length">{{ t('listing.found', { n: total }) }}</template>
    </p>

    <p v-if="errorText" class="listings__error" role="alert">{{ errorText }}</p>

    <ListingGridSkeleton v-if="loading && !items.length" :count="8" />
    <div v-else-if="items.length" class="card-grid">
      <ListingCard v-for="item in items" :key="item.id" :listing="item" />
    </div>
    <div v-else-if="!errorText" class="listings__empty">
      <p>{{ t('listing.noMatch') }}</p>
      <RouterLink :to="{ path: '/subscriptions', query: { new: '1', ...route.query } }" class="pill-btn pill-btn--acid">{{ t('home.subscribeButton') }}</RouterLink>
    </div>

    <div v-if="hasMore" class="listings__more">
      <button type="button" class="pill-btn" :disabled="loading" @click="fetchPage(page + 1)">
        {{ loading ? t('common.loading') : t('listing.loadMore') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.listings { display: grid; gap: 18px; }
.listings__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.listings__head h1 { font-size: clamp(26px, 3vw, 36px); font-weight: 900; font-style: italic; }
.listings__links { display: flex; flex-wrap: wrap; gap: 8px; }
.listings__map { display: inline-flex; align-items: center; gap: 6px; height: 38px; padding: 0 14px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); font-weight: 800; }
.listings__count { min-height: 20px; color: var(--ink-secondary); font-size: 14px; font-weight: 700; }
.listings__error { color: var(--danger, #c0392b); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 18px; }
.listings__empty { display: grid; justify-items: center; gap: 14px; padding: 48px 16px; border: 1.5px dashed var(--rule-strong); border-radius: 16px; color: var(--ink-secondary); text-align: center; }
.listings__more { display: flex; justify-content: center; }
.pill-btn { display: inline-flex; align-items: center; gap: 6px; height: 42px; padding: 0 22px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); color: var(--ink); font-size: 14px; font-weight: 800; cursor: pointer; }
.pill-btn:disabled { opacity: .6; cursor: progress; }
.pill-btn--acid { background: var(--acid); color: var(--acid-ink); box-shadow: 2px 2px 0 var(--shadow-hard); }
</style>
