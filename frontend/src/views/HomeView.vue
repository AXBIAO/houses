<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ArrowDownRight,
  ArrowRight,
  BellRing,
  BookOpenCheck,
  CalendarDays,
  LocateFixed,
  MapPinned,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-vue-next'
import FinderSearchPanel from '@/components/listing/FinderSearchPanel.vue'
import ListingCard from '@/components/listing/ListingCard.vue'
import ListingGridSkeleton from '@/components/listing/ListingGridSkeleton.vue'
import { listingsApi } from '@/features/listings/api'
import { locateUser } from '@/features/listings/geo'
import type { HomeFeed, ListingSummary, RentType } from '@/features/listings/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'HomeView' })

const { t } = useI18n()
const feed = ref<HomeFeed | null>(null)
const quickTags = ref<string[]>([])
const loadError = ref(false)
const rentType = ref<RentType | null>(null)
const nearby = ref<ListingSummary[] | null>(null)
const locating = ref(false)
const previewListing = computed(() => feed.value?.recommended[0] ?? null)
const bySelectedType = (items: ListingSummary[]) =>
  items.filter(item => rentType.value === null || item.rentType === rentType.value).slice(0, 3)
const recommended = computed(() => bySelectedType(feed.value?.recommended ?? []))
const nearbyShown = computed(() => bySelectedType(nearby.value ?? []))

const features = [
  { icon: Search, title: 'home.featureSearchTitle', body: 'home.featureSearchBody', to: '/listings', number: '01' },
  { icon: MapPinned, title: 'home.featureMapTitle', body: 'home.featureMapBody', to: '/map', number: '02' },
  { icon: Sparkles, title: 'home.featureAiTitle', body: 'home.featureAiBody', to: '/ai', number: '03' },
  { icon: BellRing, title: 'home.featureAlertsTitle', body: 'home.featureAlertsBody', to: '/subscriptions?new=1', number: '04' },
]

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
    const result = await listingsApi.search({
      lat: here.lat,
      lng: here.lng,
      radiusKm: 10,
      sort: 'distance',
      pageSize: 12,
    })
    nearby.value = result.items
  } catch {
    showToast(t('home.locateFailed'))
  } finally {
    locating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="landing">
    <section class="landing-hero" aria-labelledby="landing-title">
      <div class="landing-hero__copy">
        <p class="landing-kicker"><span class="landing-kicker__dot" />{{ t('home.landingKicker') }}</p>
        <h1 id="landing-title" class="landing-hero__title">
          {{ t('home.landingTitle') }}<br />
          <span>{{ t('home.landingAccent') }}</span>
        </h1>
        <p class="landing-hero__lead">{{ t('home.landingLead') }}</p>
        <div class="landing-hero__actions">
          <RouterLink to="/listings" class="landing-button landing-button--primary">
            {{ t('home.startLooking') }}<ArrowRight :size="17" aria-hidden="true" />
          </RouterLink>
          <RouterLink to="/ai" class="landing-button landing-button--quiet">
            <Sparkles :size="16" aria-hidden="true" />{{ t('home.tryAiSearch') }}
          </RouterLink>
        </div>
        <p class="landing-hero__note"><ShieldCheck :size="15" aria-hidden="true" />{{ t('home.noAccountNeeded') }}</p>
      </div>

      <div class="landing-hero__visual" aria-label="Houses 房源预览">
        <div class="landing-stamp" aria-hidden="true">HOUSES<br />FIND A PLACE</div>
        <div class="landing-preview">
          <div class="landing-preview__bar">
            <span class="landing-preview__dots"><i /><i /><i /></span>
            <span>{{ t('home.previewLabel') }}</span>
            <span class="landing-preview__live"><i />{{ t('home.previewLive') }}</span>
          </div>
          <div class="landing-preview__body">
            <div class="landing-preview__topline">
              <span class="landing-preview__eyebrow">{{ t('home.previewEyebrow') }}</span>
              <span class="landing-preview__counter">{{ t('home.previewCounter') }}</span>
            </div>
            <div class="landing-preview__search">
              <Search :size="17" aria-hidden="true" />
              <span>{{ t('home.previewQuery') }}</span>
              <span class="landing-preview__search-go"><ArrowRight :size="15" aria-hidden="true" /></span>
            </div>
            <div class="landing-preview__chips">
              <span>{{ t('home.previewChipOne') }}</span><span>{{ t('home.previewChipTwo') }}</span><span>{{ t('home.previewChipThree') }}</span>
            </div>
            <div v-if="previewListing" class="landing-preview__listing">
              <ListingCard :listing="previewListing" />
            </div>
            <div v-else-if="!loadError" class="landing-preview__loading"><ListingGridSkeleton :count="1" /></div>
            <div v-else class="landing-preview__offline">
              <Search :size="18" aria-hidden="true" />{{ t('home.previewOffline') }}
            </div>
            <div class="landing-preview__foot">
              <span><MapPinned :size="14" aria-hidden="true" />{{ t('home.previewMap') }}</span>
              <ArrowDownRight :size="18" aria-hidden="true" />
            </div>
          </div>
        </div>
        <div class="landing-note-card"><CalendarDays :size="17" aria-hidden="true" /><span>{{ t('home.previewDates') }}</span></div>
      </div>
    </section>

    <section class="landing-search" aria-label="房源搜索">
      <div class="landing-search__heading">
        <span class="landing-section-index">01 / {{ t('home.searchSection') }}</span>
        <span>{{ t('home.searchHint') }}</span>
      </div>
      <FinderSearchPanel :tags="quickTags" @type-change="rentType = $event" />
    </section>

    <section class="landing-features" aria-labelledby="features-title">
      <div class="landing-section-head">
        <div>
          <p class="landing-section-index">02 / {{ t('home.featuresKicker') }}</p>
          <h2 id="features-title">{{ t('home.featuresTitle') }}</h2>
        </div>
        <p>{{ t('home.featuresLead') }}</p>
      </div>
      <div class="feature-grid">
        <RouterLink v-for="feature in features" :key="feature.number" :to="feature.to" class="feature-card">
          <div class="feature-card__top"><span>{{ feature.number }}</span><component :is="feature.icon" :size="21" aria-hidden="true" /></div>
          <h3>{{ t(feature.title) }}</h3>
          <p>{{ t(feature.body) }}</p>
          <span class="feature-card__arrow"><ArrowRight :size="16" aria-hidden="true" /></span>
        </RouterLink>
      </div>
    </section>

    <section class="landing-audience" aria-label="租客和房东">
      <article class="audience-card audience-card--renter">
        <p class="landing-section-index">{{ t('home.renterLabel') }}</p>
        <h2>{{ t('home.renterTitle') }}</h2>
        <p class="audience-card__body">{{ t('home.renterBody') }}</p>
        <ul>
          <li><span>01</span>{{ t('home.renterPointOne') }}</li>
          <li><span>02</span>{{ t('home.renterPointTwo') }}</li>
          <li><span>03</span>{{ t('home.renterPointThree') }}</li>
        </ul>
        <RouterLink to="/listings" class="text-link">{{ t('home.exploreListings') }}<ArrowRight :size="16" aria-hidden="true" /></RouterLink>
        <div class="audience-card__scribble" aria-hidden="true">01</div>
      </article>
      <article class="audience-card audience-card--landlord">
        <p class="landing-section-index">{{ t('home.landlordLabel') }}</p>
        <h2>{{ t('home.landlordTitle') }}</h2>
        <p class="audience-card__body">{{ t('home.landlordBody') }}</p>
        <div class="landlord-flow" aria-label="房东管理流程">
          <div><Search :size="17" aria-hidden="true" /><span>{{ t('home.flowListings') }}</span></div>
          <i /><div><BookOpenCheck :size="17" aria-hidden="true" /><span>{{ t('home.flowLeases') }}</span></div>
          <i /><div><CalendarDays :size="17" aria-hidden="true" /><span>{{ t('home.flowBills') }}</span></div>
        </div>
        <div class="record-only"><ShieldCheck :size="17" aria-hidden="true" /><span>{{ t('home.recordOnly') }}</span></div>
        <RouterLink to="/landlord" class="text-link">{{ t('home.landlordLearnMore') }}<ArrowRight :size="16" aria-hidden="true" /></RouterLink>
        <div class="audience-card__scribble" aria-hidden="true">02</div>
      </article>
    </section>

    <section class="landing-listings" aria-labelledby="listings-title">
      <div class="landing-section-head landing-section-head--listings">
        <div>
          <p class="landing-section-index">03 / {{ t('home.liveInventory') }}</p>
          <h2 id="listings-title">{{ t('brand.todayUpdates') }}</h2>
        </div>
        <RouterLink to="/listings" class="text-link">{{ t('home.viewAll') }}<ArrowRight :size="16" aria-hidden="true" /></RouterLink>
      </div>
      <div v-if="loadError" class="listing-state" role="status">
        <span>{{ t('home.listingsUnavailable') }}</span>
        <button type="button" @click="load">{{ t('common.retry') }}</button>
      </div>
      <ListingGridSkeleton v-else-if="!feed" :count="3" />
      <div v-else-if="feed.today.length" class="listing-grid">
        <ListingCard v-for="item in feed.today.slice(0, 3)" :key="item.id" :listing="item" />
      </div>
      <p v-else class="listing-state">{{ t('common.empty') }}</p>
    </section>

    <section class="landing-content-block" aria-labelledby="recommended-title">
      <div class="landing-section-head landing-section-head--compact">
        <div>
          <p class="landing-section-index">04 / {{ t('home.recommended') }}</p>
          <h2 id="recommended-title">{{ t('home.recommended') }}</h2>
        </div>
        <RouterLink :to="{ path: '/listings', query: { recommended: 'true' } }" class="text-link">
          {{ t('home.viewAll') }}<ArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </div>
      <ListingGridSkeleton v-if="!feed && !loadError" :count="3" />
      <div v-else-if="recommended.length" class="listing-grid">
        <ListingCard v-for="item in recommended" :key="item.id" :listing="item" />
      </div>
      <p v-else-if="feed" class="listing-state">{{ t('common.empty') }}</p>
    </section>

    <section class="landing-content-block" aria-labelledby="nearby-title">
      <div class="landing-section-head landing-section-head--compact">
        <div>
          <p class="landing-section-index">05 / {{ t('home.nearby') }}</p>
          <h2 id="nearby-title">{{ t('home.nearby') }}</h2>
        </div>
        <RouterLink to="/map" class="text-link">{{ t('navigation.map') }}<ArrowRight :size="16" aria-hidden="true" /></RouterLink>
      </div>
      <div v-if="nearbyShown.length" class="listing-grid">
        <ListingCard v-for="item in nearbyShown" :key="item.id" :listing="item" />
      </div>
      <div v-else class="nearby-prompt">
        <p>{{ nearby ? t('home.nearbyEmpty', { n: 10 }) : t('home.nearbyHint') }}</p>
        <button type="button" class="landing-button landing-button--quiet" :disabled="locating" @click="locate">
          <LocateFixed :size="16" aria-hidden="true" />{{ locating ? t('home.locating') : t('home.locateMe') }}
        </button>
      </div>
    </section>

    <section class="subscription-banner">
      <div class="subscription-banner__icon"><BellRing :size="24" aria-hidden="true" /></div>
      <div class="subscription-banner__copy">
        <p class="landing-section-index">06 / {{ t('home.subscribeTitle') }}</p>
        <h2>{{ t('home.subscribeTitle') }}</h2>
        <p>{{ t('home.subscribeDesc') }}</p>
      </div>
      <RouterLink :to="{ path: '/subscriptions', query: { new: '1' } }" class="landing-button landing-button--primary">
        {{ t('home.subscribeButton') }}<ArrowRight :size="16" aria-hidden="true" />
      </RouterLink>
    </section>

  </div>
</template>

<style scoped>
.landing { display: grid; gap: clamp(48px, 8vw, 100px); padding: 18px 0 22px; }
.landing-hero { display: grid; grid-template-columns: minmax(0, 1.03fr) minmax(360px, .97fr); gap: clamp(28px, 6vw, 80px); align-items: start; min-height: 510px; padding: clamp(24px, 4vw, 52px) 0 12px; }
.landing-hero__copy { position: relative; z-index: 1; }
.landing-kicker, .landing-section-index { display: flex; align-items: center; gap: 9px; margin: 0; color: var(--ink-secondary); font-size: 11px; font-weight: 900; letter-spacing: .11em; text-transform: uppercase; }
.landing-kicker { width: fit-content; padding: 8px 11px; border: 1.5px solid var(--rule-strong); background: var(--paper-raised); color: var(--ink); box-shadow: 2px 2px 0 var(--shadow-hard); }
.landing-kicker__dot, .landing-preview__live i { width: 7px; height: 7px; border-radius: 50%; background: #8db324; box-shadow: 0 0 0 3px color-mix(in srgb, #8db324 18%, transparent); }
.landing-hero__title { max-width: 690px; margin: 24px 0 18px; color: var(--ink); font-size: clamp(46px, 5.4vw, 64px); font-weight: 950; line-height: 1.02; letter-spacing: -.055em; }
.landing-hero__title span { position: relative; display: inline-block; z-index: 0; }
.landing-hero__title span::after { content: ''; position: absolute; z-index: -1; left: -3px; right: -7px; bottom: 3px; height: .28em; background: var(--acid); transform: skewX(-8deg); }
.landing-hero__lead { max-width: 520px; margin: 0; color: var(--ink-secondary); font-size: clamp(16px, 1.7vw, 19px); line-height: 1.8; }
.landing-hero__actions { display: flex; flex-wrap: wrap; gap: 11px; margin-top: 28px; }
.landing-button { display: inline-flex; align-items: center; justify-content: center; gap: 11px; min-height: 48px; padding: 0 19px; border: 1.5px solid var(--rule-strong); border-radius: 5px; color: var(--ink); text-decoration: none; font-size: 14px; font-weight: 900; transition: transform .16s ease, box-shadow .16s ease, background .16s ease; }
.landing-button:hover { transform: translate(-2px, -2px); box-shadow: 4px 4px 0 var(--shadow-hard); }
.landing-button--primary { background: var(--acid); box-shadow: 3px 3px 0 var(--shadow-hard); }
.landing-button--quiet { background: var(--paper-raised); }
.landing-button--dark { background: var(--ink); color: var(--paper-raised); border-color: var(--ink); }
.landing-hero__note { display: flex; align-items: center; gap: 7px; margin: 18px 0 0; color: var(--ink-muted); font-size: 12px; font-weight: 700; }
.landing-hero__visual { position: relative; min-width: 0; padding: 22px 20px 30px 30px; }
.landing-preview { position: relative; z-index: 1; overflow: hidden; max-width: 440px; margin-left: auto; border: 2px solid var(--rule-strong); border-radius: 8px; background: var(--paper-raised); box-shadow: 8px 8px 0 var(--shadow-hard); transform: rotate(1.2deg); }
.landing-preview__bar { display: flex; align-items: center; justify-content: space-between; height: 38px; padding: 0 12px; border-bottom: 1.5px solid var(--rule-strong); color: var(--ink-muted); font-size: 10px; font-weight: 800; letter-spacing: .05em; }
.landing-preview__dots { display: inline-flex; gap: 4px; }
.landing-preview__dots i { width: 7px; height: 7px; border: 1px solid var(--rule-strong); border-radius: 50%; background: var(--paper-muted); }
.landing-preview__live { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-secondary); }
.landing-preview__live i { width: 6px; height: 6px; }
.landing-preview__body { padding: 17px 17px 14px; }
.landing-preview__topline { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.landing-preview__eyebrow { color: var(--ink); font-size: 11px; font-weight: 900; letter-spacing: .04em; }
.landing-preview__counter { padding: 4px 7px; border: 1px solid var(--rule-strong); border-radius: 99px; background: var(--acid); color: var(--acid-ink); font-size: 9px; font-weight: 900; }
.landing-preview__search { display: flex; align-items: center; gap: 9px; min-height: 43px; padding: 0 8px 0 11px; border: 1.5px solid var(--rule-strong); border-radius: 5px; color: var(--ink-muted); font-size: 11px; }
.landing-preview__search-go { display: grid; place-items: center; width: 29px; height: 29px; margin-left: auto; border: 1px solid var(--rule-strong); border-radius: 4px; background: var(--acid); color: var(--acid-ink); }
.landing-preview__chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 9px 0 13px; }
.landing-preview__chips span { padding: 4px 8px; border: 1px solid var(--rule); border-radius: 99px; color: var(--ink-secondary); font-size: 9px; font-weight: 800; }
.landing-preview__listing :deep(.listing-card) { min-width: 0; }
.landing-preview__loading { min-height: 160px; }
.landing-preview__offline { display: flex; align-items: center; justify-content: center; gap: 9px; min-height: 140px; border: 1px dashed var(--rule-strong); color: var(--ink-muted); font-size: 12px; }
.landing-preview__foot { display: flex; align-items: center; justify-content: space-between; margin-top: 13px; color: var(--ink-secondary); font-size: 10px; font-weight: 800; }
.landing-preview__foot span { display: inline-flex; align-items: center; gap: 6px; }
.landing-stamp { position: absolute; top: 0; right: 0; z-index: 2; padding: 10px 12px; border: 1.5px solid var(--rule-strong); background: var(--acid); color: var(--acid-ink); font-family: var(--font-display, inherit); font-size: 10px; font-weight: 900; line-height: 1.25; letter-spacing: .08em; transform: rotate(7deg); }
.landing-note-card { position: absolute; bottom: 0; left: 0; z-index: 2; display: flex; align-items: center; gap: 8px; max-width: 230px; padding: 10px 13px; border: 1.5px solid var(--rule-strong); background: var(--paper-raised); box-shadow: 3px 3px 0 var(--shadow-hard); color: var(--ink-secondary); font-size: 10px; font-weight: 800; transform: rotate(-2deg); }
.landing-note-card svg { flex: none; color: var(--ink); }
.landing-search { display: grid; gap: 12px; }
.landing-search__heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; color: var(--ink-muted); font-size: 12px; font-weight: 700; }
.landing-search :deep(.finder) { margin: 0; }
.landing-section-head { display: flex; align-items: end; justify-content: space-between; gap: 30px; margin-bottom: 21px; }
.landing-section-head h2 { margin: 9px 0 0; color: var(--ink); font-size: clamp(27px, 4vw, 42px); font-weight: 950; line-height: 1.08; letter-spacing: -.045em; }
.landing-section-head > p { max-width: 340px; margin: 0; color: var(--ink-secondary); font-size: 13px; line-height: 1.7; }
.feature-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1.5px solid var(--rule-strong); background: var(--paper-raised); box-shadow: 4px 4px 0 var(--shadow-hard); }
.feature-card { position: relative; display: flex; min-height: 210px; flex-direction: column; padding: 19px; color: var(--ink); text-decoration: none; transition: background .16s ease; }
.feature-card + .feature-card { border-left: 1.5px solid var(--rule-strong); }
.feature-card:hover { background: var(--acid-soft); }
.feature-card__top { display: flex; align-items: center; justify-content: space-between; color: var(--ink-muted); }
.feature-card__top > span { font-family: ui-monospace, monospace; font-size: 11px; font-weight: 800; }
.feature-card__top svg { color: var(--ink); }
.feature-card h3 { margin: 27px 0 8px; font-size: 18px; font-weight: 900; letter-spacing: -.02em; }
.feature-card p { max-width: 230px; margin: 0; color: var(--ink-secondary); font-size: 12px; line-height: 1.7; }
.feature-card__arrow { position: absolute; right: 17px; bottom: 16px; display: grid; place-items: center; width: 28px; height: 28px; border: 1px solid var(--rule-strong); border-radius: 50%; }
.landing-audience { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.audience-card { position: relative; overflow: hidden; min-height: 370px; padding: clamp(22px, 4vw, 38px); border: 1.5px solid var(--rule-strong); box-shadow: 4px 4px 0 var(--shadow-hard); }
.audience-card--renter { background: var(--acid); color: var(--acid-ink); }
.audience-card--landlord { background: var(--paper-raised); }
.audience-card h2 { position: relative; z-index: 1; max-width: 440px; margin: 16px 0 10px; font-size: clamp(26px, 3.5vw, 39px); font-weight: 950; line-height: 1.08; letter-spacing: -.045em; }
.audience-card__body { position: relative; z-index: 1; max-width: 470px; margin: 0; color: var(--ink-secondary); font-size: 13px; line-height: 1.75; }
.audience-card--renter .audience-card__body { color: color-mix(in srgb, var(--acid-ink) 78%, transparent); }
.audience-card ul { position: relative; z-index: 1; display: grid; gap: 8px; margin: 22px 0 20px; padding: 0; list-style: none; }
.audience-card li { display: flex; align-items: center; gap: 12px; font-size: 12px; font-weight: 800; }
.audience-card li span { font-family: ui-monospace, monospace; font-size: 10px; opacity: .62; }
.text-link { position: relative; z-index: 1; display: inline-flex; align-items: center; gap: 9px; width: fit-content; color: var(--ink); font-size: 12px; font-weight: 900; text-decoration: none; }
.text-link:hover { text-decoration: underline; text-underline-offset: 4px; }
.audience-card__scribble { position: absolute; right: -18px; bottom: -68px; color: color-mix(in srgb, var(--ink) 8%, transparent); font-family: ui-monospace, monospace; font-size: 220px; font-weight: 950; line-height: 1; }
.landlord-flow { position: relative; z-index: 1; display: flex; align-items: center; gap: 9px; margin: 24px 0 13px; }
.landlord-flow > div { display: flex; min-width: 0; flex: 1; flex-direction: column; align-items: center; gap: 7px; padding: 12px 7px; border: 1.5px solid var(--rule-strong); background: var(--paper); color: var(--ink); font-size: 10px; font-weight: 900; }
.landlord-flow > i { width: 13px; height: 1px; flex: none; background: var(--rule-strong); }
.record-only { position: relative; z-index: 1; display: flex; align-items: center; gap: 7px; margin: 0 0 17px; color: var(--ink-secondary); font-size: 10px; font-weight: 800; }
.record-only svg { flex: none; }
.landing-section-head--listings { align-items: end; }
.landing-section-head--listings .text-link { margin-bottom: 5px; }
.listing-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
.listing-state { display: flex; align-items: center; justify-content: space-between; min-height: 90px; padding: 18px; border: 1px dashed var(--rule-strong); color: var(--ink-secondary); font-size: 13px; }
.listing-state button { padding: 8px 14px; border: 1px solid var(--rule-strong); border-radius: 99px; background: var(--paper-raised); color: var(--ink); font-weight: 800; cursor: pointer; }
.landing-content-block { display: grid; gap: 18px; }
.landing-section-head--compact { margin-bottom: 0; }
.landing-section-head--compact .text-link { margin-bottom: 4px; }
.nearby-prompt { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; min-height: 88px; padding: 18px 20px; border: 1.5px dashed var(--rule-strong); color: var(--ink-secondary); }
.nearby-prompt p { margin: 0; font-size: 13px; line-height: 1.65; }
.nearby-prompt .landing-button { min-height: 42px; }
.nearby-prompt .landing-button:disabled { cursor: progress; opacity: .65; }
.subscription-banner { display: flex; flex-wrap: wrap; align-items: center; gap: 18px; padding: clamp(20px, 4vw, 32px); border: 1.5px solid var(--rule-strong); background: var(--acid-soft); box-shadow: 4px 4px 0 var(--shadow-hard); }
.subscription-banner__icon { display: grid; place-items: center; width: 54px; height: 54px; flex: none; border: 1.5px solid var(--rule-strong); background: var(--acid); color: var(--acid-ink); }
.subscription-banner__copy { flex: 1; min-width: 220px; }
.subscription-banner__copy h2 { margin: 6px 0; font-size: clamp(20px, 3vw, 28px); font-weight: 950; letter-spacing: -.03em; }
.subscription-banner__copy > p:last-child { margin: 0; color: var(--ink-secondary); font-size: 13px; line-height: 1.6; }
:root[data-theme='dark'] .subscription-banner { background: var(--paper-raised); }
@media (max-width: 900px) {
  .landing-hero { grid-template-columns: minmax(0, 1fr) minmax(300px, .9fr); gap: 16px; }
  .landing-hero__title { font-size: clamp(43px, 5.4vw, 64px); }
  .feature-card { padding: 15px; }
  .feature-card h3 { font-size: 16px; }
}
@media (max-width: 680px) {
  .landing { gap: 54px; padding-top: 4px; }
  .landing-hero { grid-template-columns: 1fr; min-height: auto; gap: 14px; padding-top: 23px; }
  .landing-hero__title { margin-top: 20px; font-size: clamp(42px, 11vw, 58px); }
  .landing-hero__visual { width: 100%; max-width: 470px; justify-self: center; padding: 20px 13px 28px 18px; }
  .landing-preview { max-width: 100%; }
  .landing-search__heading { align-items: flex-start; flex-direction: column; gap: 5px; }
  .landing-section-head { align-items: flex-start; flex-direction: column; gap: 11px; }
  .feature-grid { grid-template-columns: 1fr 1fr; }
  .feature-card { min-height: 185px; padding: 15px; }
  .feature-card + .feature-card { border-left: 0; }
  .feature-card:nth-child(even) { border-left: 1.5px solid var(--rule-strong); }
  .feature-card:nth-child(n + 3) { border-top: 1.5px solid var(--rule-strong); }
  .landing-audience { grid-template-columns: 1fr; }
  .audience-card { min-height: 350px; }
  .listing-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .landing-button, .feature-card { transition: none; }
}
</style>
