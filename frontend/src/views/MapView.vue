<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { List, LocateFixed, SlidersHorizontal } from 'lucide-vue-next'
import HouseMap from '@/components/map/HouseMap.vue'
import type { MapBounds, MapMarker } from '@/components/map/LeafletMap.vue'
import ListingCard from '@/components/listing/ListingCard.vue'
import ListingFilterBar from '@/components/listing/ListingFilterBar.vue'
import { listingsApi } from '@/features/listings/api'
import { locateUser } from '@/features/listings/geo'
import { parseSearch, toQuery, type SearchState } from '@/features/listings/searchQuery'
import { useFacets } from '@/features/listings/useFacets'
import type { ListingSummary } from '@/features/listings/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'MapView' })

/** 城市列表还没取到时的默认视野；取到后以房源最多的城市为中心 */
const DEFAULT_CENTER: [number, number] = [30.6598, 104.0657]
const DEFAULT_ZOOM = 12
const CITY_ZOOM = 11

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const facets = useFacets()

const search = computed(() => parseSearch(route.query))
const bounds = ref<MapBounds | null>(null)
const items = ref<ListingSummary[]>([])
const total = ref(0)
const truncated = ref(false)
const loading = ref(false)
const failed = ref(false)
/** 当前选中的小区 */
const activeEstate = ref<number | null>(null)
const filtersOpen = ref(false)
const mapRef = ref<InstanceType<typeof HouseMap> | null>(null)
const cities = computed(() => facets.value?.cities ?? [])
const center = computed<[number, number]>(() => (cities.value[0] ? [cities.value[0].lat, cities.value[0].lng] : DEFAULT_CENTER))
const listRef = ref<HTMLElement | null>(null)
let controller: AbortController | null = null

/** 同一小区坐标相同，按小区合并成一个标记：单套显示价格，多套显示最低价与套数 */
const markers = computed<MapMarker[]>(() => {
  const groups = new Map<number, ListingSummary[]>()
  for (const item of items.value) groups.set(item.estateId, [...(groups.get(item.estateId) ?? []), item])
  return [...groups.entries()].map(([estateId, group]) => {
    const cheapest = group.reduce((a, b) => (a.price <= b.price ? a : b))
    const unit = cheapest.rentType === 'short' ? t('common.perNight') : ''
    const price = `¥${cheapest.price.toLocaleString()}${unit}`
    const kinds = new Set(group.map(g => g.rentType))
    return {
      id: estateId, lat: cheapest.lat, lng: cheapest.lng,
      kind: kinds.size === 1 ? cheapest.rentType : 'mixed',
      // 月价与晚价不可比，混合类型的小区只显示套数
      label: kinds.size > 1
        ? t('map.groupMixed', { name: cheapest.community, n: group.length })
        : group.length > 1 ? t('map.groupLabel', { price, n: group.length }) : price,
    }
  })
})

function applySearch(next: SearchState) {
  void router.replace({ query: toQuery(next) })
}

async function load() {
  if (!bounds.value || route.name !== 'map') return
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  failed.value = false
  const b = bounds.value
  const bbox = [b.minLng, b.minLat, b.maxLng, b.maxLat].map(n => n.toFixed(5)).join(',')
  try {
    const res = await listingsApi.map({ ...toQuery(search.value), bbox }, current.signal)
    items.value = res.items
    total.value = res.total
    truncated.value = res.truncated
  } catch (error) {
    if ((error as Error).name !== 'AbortError') failed.value = true
  } finally {
    if (controller === current) loading.value = false
  }
}

async function select(estateId: number) {
  activeEstate.value = estateId
  await nextTick()
  listRef.value?.querySelector(`[data-estate="${estateId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

function goCity(lat: number, lng: number) {
  activeEstate.value = null
  mapRef.value?.flyTo(lat, lng, CITY_ZOOM)
}

async function locate() {
  try {
    const here = await locateUser()
    mapRef.value?.flyTo(here.lat, here.lng, 14)
  } catch {
    showToast(t('home.locateFailed'))
  }
}

watch(bounds, load)
watch(() => JSON.stringify(toQuery(search.value)), load)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="map-page">
    <header class="map-page__head">
      <h1>{{ t('navigation.map') }}</h1>
      <div class="map-page__actions">
        <button type="button" class="pill-btn" :aria-expanded="filtersOpen" @click="filtersOpen = !filtersOpen">
          <SlidersHorizontal :size="16" aria-hidden="true" />{{ t('filters.title') }}
        </button>
        <button type="button" class="pill-btn" @click="locate"><LocateFixed :size="16" aria-hidden="true" />{{ t('home.locateMe') }}</button>
        <RouterLink :to="{ path: '/listings', query: route.query }" class="pill-btn"><List :size="16" aria-hidden="true" />{{ t('navigation.listings') }}</RouterLink>
      </div>
    </header>

    <nav v-if="cities.length > 1" class="map-page__cities" :aria-label="t('map.cities')">
      <button v-for="city in cities" :key="city.value" type="button" class="pill-btn" @click="goCity(city.lat, city.lng)">
        {{ city.value }}<span class="map-page__city-count">{{ city.count }}</span>
      </button>
    </nav>

    <ListingFilterBar v-if="filtersOpen" :model-value="search" :facets="facets" :show-sort="false" @update:model-value="applySearch" />

    <div class="map-page__body">
      <div class="map-page__map">
        <HouseMap ref="mapRef" :center="center" :zoom="DEFAULT_ZOOM" :markers="markers" :active-id="activeEstate" @bounds="bounds = $event" @select="select" />
        <p class="map-page__status" aria-live="polite">
          <template v-if="loading">{{ t('common.loading') }}</template>
          <template v-else-if="failed">{{ t('common.error') }}</template>
          <template v-else>{{ truncated ? t('map.truncated', { shown: items.length, n: total }) : t('map.inView', { n: total }) }}</template>
        </p>
      </div>
      <aside ref="listRef" class="map-page__list" :aria-label="t('map.inView', { n: total })">
        <p v-if="!loading && !items.length" class="map-page__empty">{{ t('map.empty') }}</p>
        <div
          v-for="item in items" :key="item.id" :data-estate="item.estateId"
          class="map-page__item" :class="{ 'is-active': activeEstate === item.estateId }"
          @mouseenter="activeEstate = item.estateId"
        >
          <ListingCard :listing="item" />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.map-page { display: grid; gap: 14px; }
.map-page__head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.map-page__head h1 { font-size: clamp(26px, 3vw, 36px); font-weight: 900; font-style: italic; }
.map-page__actions { display: flex; flex-wrap: wrap; gap: 8px; }
.pill-btn { display: inline-flex; align-items: center; gap: 6px; height: 38px; padding: 0 14px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); color: var(--ink); font-size: 14px; font-weight: 800; cursor: pointer; }
.pill-btn[aria-expanded='true'] { background: var(--acid); color: var(--acid-ink); }
.map-page__cities { display: flex; flex-wrap: wrap; gap: 8px; }
.map-page__city-count { padding: 0 7px; border-radius: 999px; background: var(--paper); font-size: 12px; }
.map-page__body { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; height: calc(100dvh - 300px); min-height: 420px; }
.map-page__map { position: relative; border: 2px solid var(--rule-strong); border-radius: 18px; overflow: hidden; box-shadow: 4px 4px 0 var(--shadow-hard); }
.map-page__status { position: absolute; left: 12px; top: 12px; z-index: 500; padding: 4px 12px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); font-size: 13px; font-weight: 800; pointer-events: none; }
.map-page__list { display: grid; align-content: start; gap: 14px; overflow-y: auto; padding: 2px 6px 8px 2px; }
.map-page__item { border-radius: 16px; outline: 3px solid transparent; outline-offset: 2px; transition: outline-color 140ms ease; }
.map-page__item.is-active { outline-color: var(--acid-strong); }
.map-page__empty { padding: 24px; border: 1.5px dashed var(--rule-strong); border-radius: 14px; color: var(--ink-secondary); text-align: center; }
@media (max-width: 960px) {
  .map-page__body { grid-template-columns: 1fr; height: auto; }
  .map-page__map { height: 56dvh; }
  .map-page__list { overflow: visible; }
}
</style>
