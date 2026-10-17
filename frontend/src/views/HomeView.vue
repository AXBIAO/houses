<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { BellRing, LocateFixed, Sparkles } from 'lucide-vue-next'
import FinderSearchPanel from '@/components/listing/FinderSearchPanel.vue'
import ListingCard from '@/components/listing/ListingCard.vue'
import ListingGridSkeleton from '@/components/listing/ListingGridSkeleton.vue'
import { listingsApi } from '@/features/listings/api'
import { locateUser } from '@/features/listings/geo'
import type { HomeFeed, ListingSummary, RentType } from '@/features/listings/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'HomeView' })

const NEARBY_RADIUS_KM = 10
const SECTION_SIZE = 4

const { t } = useI18n()
const rentType = ref<RentType | null>(null)
const feed = ref<HomeFeed | null>(null)
const quickTags = ref<string[]>([])
const loadError = ref(false)
const nearby = ref<ListingSummary[] | null>(null)
const locating = ref(false)

const ofType = (items: ListingSummary[]) =>
  items.filter(l => rentType.value === null || l.rentType === rentType.value).slice(0, SECTION_SIZE)
const todayUpdates = computed(() => ofType(feed.value?.today ?? []))
const recommended = computed(() => ofType(feed.value?.recommended ?? []))
const nearbyShown = computed(() => (nearby.value ? ofType(nearby.value) : []))

async function load() {
  loadError.value = false
  try {
    const [home, facets] = await Promise.all([listingsApi.home(), listingsApi.facets()])
    feed.value = home
    quickTags.value = facets.tags.slice(0, 8).map(f => f.value)
  } catch {
    loadError.value = true
  }
}

async function locate() {
  locating.value = true
  try {
    const here = await locateUser()
    const page = await listingsApi.search({ lat: here.lat, lng: here.lng, radiusKm: NEARBY_RADIUS_KM, sort: 'distance', pageSize: 12 })
    nearby.value = page.items
  } catch {
    showToast(t('home.locateFailed'))
  } finally {
    locating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="home">
    <section class="hero">
      <p class="hero__kicker">{{ t('brand.name') }}</p>
      <h1 class="hero__title">{{ t('brand.slogan') }}</h1>
      <p class="hero__lead">{{ t('brand.sloganSecondary') }}</p>
    </section>

    <FinderSearchPanel :tags="quickTags" @type-change="rentType = $event" />

    <div v-if="loadError" class="block__error" role="alert">
      <span>{{ t('common.error') }}</span>
      <button type="button" class="pill-btn" @click="load">{{ t('common.retry') }}</button>
    </div>

    <section class="block">
      <header class="block__head">
        <h2 class="block__title"><span class="block__mark" aria-hidden="true" />{{ t('brand.todayUpdates') }}</h2>
        <span v-if="feed?.todayCount" class="block__badge">{{ t('home.todayCount', { n: feed.todayCount }) }}</span>
        <RouterLink to="/listings" class="block__more">{{ t('home.viewAll') }}</RouterLink>
      </header>
      <ListingGridSkeleton v-if="!feed && !loadError" :count="SECTION_SIZE" />
      <div v-else-if="todayUpdates.length" class="card-grid">
        <ListingCard v-for="item in todayUpdates" :key="item.id" :listing="item" />
      </div>
      <p v-else-if="feed" class="block__empty">{{ t('common.empty') }}</p>
    </section>

    <section class="block">
      <header class="block__head">
        <h2 class="block__title"><Sparkles :size="20" aria-hidden="true" />{{ t('home.recommended') }}</h2>
        <RouterLink :to="{ path: '/listings', query: { recommended: 'true' } }" class="block__more">{{ t('home.viewAll') }}</RouterLink>
      </header>
      <ListingGridSkeleton v-if="!feed && !loadError" :count="SECTION_SIZE" />
      <div v-else-if="recommended.length" class="card-grid">
        <ListingCard v-for="item in recommended" :key="item.id" :listing="item" />
      </div>
      <p v-else-if="feed" class="block__empty">{{ t('common.empty') }}</p>
    </section>

    <section class="block">
      <header class="block__head">
        <h2 class="block__title"><LocateFixed :size="20" aria-hidden="true" />{{ t('home.nearby') }}</h2>
        <RouterLink to="/map" class="block__more">{{ t('navigation.map') }}</RouterLink>
      </header>
      <div v-if="nearbyShown.length" class="card-grid">
        <ListingCard v-for="item in nearbyShown" :key="item.id" :listing="item" />
      </div>
      <div v-else class="block__locate">
        <p>{{ nearby ? t('home.nearbyEmpty', { n: NEARBY_RADIUS_KM }) : t('home.nearbyHint') }}</p>
        <button type="button" class="pill-btn" :disabled="locating" @click="locate">
          <LocateFixed :size="16" aria-hidden="true" />{{ locating ? t('home.locating') : t('home.locateMe') }}
        </button>
      </div>
    </section>

    <section class="subscribe">
      <BellRing class="subscribe__icon" :size="32" aria-hidden="true" />
      <div class="subscribe__text">
        <h2>{{ t('home.subscribeTitle') }}</h2>
        <p>{{ t('home.subscribeDesc') }}</p>
      </div>
      <RouterLink :to="{ path: '/subscriptions', query: { new: '1' } }" class="pill-btn pill-btn--acid">{{ t('home.subscribeButton') }}</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.home { display: grid; gap: 28px; }
.hero { display: grid; gap: 6px; padding-top: 12px; }
.hero__kicker { width: fit-content; padding: 2px 10px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
.hero__title { font-size: clamp(34px, 6vw, 64px); font-weight: 900; line-height: 1.05; letter-spacing: -.02em; }
.hero__lead { position: relative; width: fit-content; font-size: clamp(18px, 2.4vw, 26px); font-weight: 800; color: var(--ink-secondary); }
.hero__lead::after { content: ''; position: absolute; left: 0; right: 0; bottom: 2px; height: 10px; z-index: -1; background: var(--acid); transform: skewX(-12deg); }
.block { display: grid; gap: 14px; }
.block__head { display: flex; align-items: center; gap: 12px; }
.block__title { display: inline-flex; align-items: center; gap: 8px; font-size: clamp(20px, 2.4vw, 26px); font-weight: 900; font-style: italic; }
.block__mark { width: 10px; height: 22px; background: var(--acid); border: 1.5px solid var(--rule-strong); transform: skewX(-12deg); }
.block__badge { padding: 2px 10px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--acid); color: var(--acid-ink); font-size: 12px; font-weight: 800; }
.block__more { margin-left: auto; color: var(--ink-secondary); font-size: 14px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
.block__empty { color: var(--ink-muted); }
.block__error { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 18px; border: 1.5px solid var(--danger, #c0392b); border-radius: 12px; color: var(--danger, #c0392b); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 18px; }
.block__locate { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 18px; border: 1.5px dashed var(--rule-strong); border-radius: 14px; color: var(--ink-secondary); }
.pill-btn { display: inline-flex; align-items: center; gap: 6px; height: 40px; padding: 0 16px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); color: var(--ink); font-size: 14px; font-weight: 800; cursor: pointer; text-decoration: none; }
.pill-btn:disabled { opacity: .6; cursor: progress; }
.pill-btn--acid { background: var(--acid); color: var(--acid-ink); box-shadow: 2px 2px 0 var(--shadow-hard); }
.subscribe { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 22px; border: 2px solid var(--rule-strong); border-radius: 18px; background: var(--acid-soft); box-shadow: 4px 4px 0 var(--shadow-hard); }
.subscribe__icon { flex: none; }
.subscribe__text { flex: 1; min-width: 220px; }
.subscribe__text h2 { font-size: 20px; font-weight: 900; }
.subscribe__text p { color: var(--ink-secondary); font-size: 14px; }
:root[data-theme='dark'] .subscribe { background: var(--paper-raised); }
:root[data-theme='dark'] .hero__lead::after { opacity: .35; }
</style>
