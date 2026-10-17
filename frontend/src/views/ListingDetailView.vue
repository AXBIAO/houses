<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, CalendarX2, MapPin } from 'lucide-vue-next'
import InquiryForm from '@/components/listing/InquiryForm.vue'
import LeafletMap from '@/components/map/LeafletMap.vue'
import { listingsApi } from '@/features/listings/api'
import { parseSearch } from '@/features/listings/searchQuery'
import type { ListingDetail } from '@/features/listings/types'
import { ApiError } from '@/services/http/apiClient'
import { setJsonLd, setPageHead } from '@/features/seo/pageHead'

defineOptions({ name: 'ListingDetailView' })

const { t } = useI18n()
const route = useRoute()
const listing = ref<ListingDetail | null>(null)
const notFound = ref(false)
const failed = ref(false)

const today = new Date().toISOString().slice(0, 10)
const id = Number(route.params.id)
const search = parseSearch(route.query)
const isShort = computed(() => listing.value?.rentType === 'short')

const facts = computed(() => {
  const l = listing.value
  if (!l) return []
  const rows: [string, string][] = [
    [t('detail.layout'), l.rentType === 'shared' ? t('listing.sharedRoom', { n: l.bedrooms }) : t('listing.layout', { rooms: l.bedrooms, halls: l.halls })],
    [t('detail.area'), t('listing.area', { n: l.area })],
  ]
  if (l.floor != null) rows.push([t('detail.floor'), l.totalFloors ? `${l.floor} / ${l.totalFloors}` : String(l.floor)])
  if (l.orientation) rows.push([t('detail.orientation'), l.orientation])
  rows.push(l.rentType === 'short'
    ? [t('detail.minStay'), t('detail.nights', { n: l.minNights })]
    : [t('detail.minStay'), t('detail.monthsN', { n: l.minMonths })])
  if (l.rentType !== 'short') rows.push([t('detail.payment'), t('detail.depositPay', { n: l.depositMonths })])
  rows.push([t('detail.availableFrom'), l.availableFrom && l.availableFrom > today ? l.availableFrom : t('detail.availableNow')])
  return rows
})
const coverStyle = computed(() => {
  const l = listing.value
  if (!l) return {}
  if (l.images[0] || l.coverUrl) return { backgroundImage: `url(${JSON.stringify(l.images[0] ?? l.coverUrl)})` }
  const h = (l.id * 47) % 360
  return { background: `linear-gradient(135deg, hsl(${h} 70% 82%), hsl(${(h + 40) % 360} 65% 66%))` }
})

onMounted(async () => {
  if (!Number.isInteger(id) || id <= 0) {
    notFound.value = true
    return
  }
  try {
    listing.value = await listingsApi.detail(id)
    applyHead(listing.value)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound.value = true
    else failed.value = true
    setPageHead({ title: t('detail.notFound'), noindex: true })
  }
})
onBeforeUnmount(() => setJsonLd(null))

/** 标题、描述与 schema.org 结构化数据，便于搜索引擎展示房源信息 */
function applyHead(l: ListingDetail) {
  const unit = l.rentType === 'short' ? t('common.perNight') : t('common.perMonth')
  const description = `${t(`rentType.${l.rentType}`)} · ¥${l.price}${unit} · ${l.district} ${l.community} · ${l.area}㎡${l.tags.length ? ' · ' + l.tags.join('、') : ''}`
  setPageHead({ title: l.title, description })
  const image = l.images[0] ?? l.coverUrl
  setJsonLd({
    '@context': 'https://schema.org',
    '@type': 'Apartment',
    name: l.title,
    description: l.description || description,
    url: window.location.origin + window.location.pathname,
    ...(image ? { image: new URL(image, window.location.origin).href } : {}),
    numberOfRooms: l.bedrooms,
    floorSize: { '@type': 'QuantitativeValue', value: l.area, unitCode: 'MTK' },
    address: { '@type': 'PostalAddress', addressLocality: l.city, addressRegion: l.district, streetAddress: l.address || l.community, addressCountry: 'CN' },
    geo: { '@type': 'GeoCoordinates', latitude: l.lat, longitude: l.lng },
  })
}
</script>

<template>
  <div class="detail">
    <RouterLink :to="{ path: '/listings', query: route.query }" class="detail__back"><ArrowLeft :size="16" aria-hidden="true" />{{ t('detail.back') }}</RouterLink>

    <section v-if="notFound || failed" class="detail__missing">
      <h1>{{ notFound ? t('detail.notFound') : t('common.error') }}</h1>
      <RouterLink to="/listings" class="detail__cta">{{ t('navigation.listings') }}</RouterLink>
    </section>

    <p v-else-if="!listing" class="detail__loading">{{ t('common.loading') }}</p>

    <template v-else>
      <div class="detail__cover" :style="coverStyle">
        <span class="detail__type" :data-type="listing.rentType">{{ t(`rentType.${listing.rentType}`) }}</span>
      </div>

      <div class="detail__layout">
        <article class="detail__main">
          <header class="detail__head">
            <h1>{{ listing.title }}</h1>
            <p class="detail__place"><MapPin :size="15" aria-hidden="true" />{{ listing.city }} · {{ listing.district }} · {{ listing.community }}<template v-if="listing.address"> · {{ listing.address }}</template></p>
            <p class="detail__price"><strong>¥{{ listing.price.toLocaleString() }}</strong>{{ t(isShort ? 'common.perNight' : 'common.perMonth') }}</p>
            <ul class="detail__tags"><li v-for="tag in listing.tags" :key="tag">{{ tag }}</li></ul>
          </header>

          <dl class="detail__facts">
            <div v-for="[label, value] in facts" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div>
          </dl>

          <section v-if="listing.description" class="detail__section">
            <h2>{{ t('detail.description') }}</h2>
            <p class="detail__desc">{{ listing.description }}</p>
          </section>

          <section v-if="listing.unavailable.length" class="detail__section">
            <h2><CalendarX2 :size="18" aria-hidden="true" />{{ t('detail.booked') }}</h2>
            <ul class="detail__busy">
              <li v-for="p in listing.unavailable" :key="p.start">{{ t('detail.bookedRange', { start: p.start, end: p.end }) }}</li>
            </ul>
          </section>

          <section class="detail__section">
            <h2>{{ t('detail.location') }}</h2>
            <div class="detail__map">
              <LeafletMap :center="[listing.lat, listing.lng]" :zoom="15" :markers="[{ id: listing.id, lat: listing.lat, lng: listing.lng, label: listing.community, kind: listing.rentType }]" :active-id="listing.id" />
            </div>
          </section>
        </article>

        <aside class="detail__aside">
          <p class="detail__landlord">{{ t('detail.landlord', { name: listing.landlordName }) }}</p>
          <InquiryForm :listing-id="listing.id" :is-short="isShort" :move-in="search.moveIn" :move-out="search.moveOut" />
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail { display: grid; gap: 18px; }
.detail__back { display: inline-flex; align-items: center; gap: 6px; width: fit-content; color: var(--ink-secondary); font-weight: 700; }
.detail__missing { display: grid; justify-items: start; gap: 14px; padding: 28px; border: 2px solid var(--rule-strong); border-radius: 16px; background: var(--paper-raised); }
.detail__cta { padding: 8px 16px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--acid); color: var(--acid-ink); font-weight: 800; }
.detail__loading { color: var(--ink-muted); }
.detail__cover { position: relative; height: clamp(200px, 32vw, 360px); border: 2px solid var(--rule-strong); border-radius: 18px; background-size: cover; background-position: center; box-shadow: 4px 4px 0 var(--shadow-hard); }
.detail__type { position: absolute; left: 14px; top: 14px; padding: 4px 12px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--acid); color: var(--acid-ink); font-weight: 900; }
.detail__type[data-type='short'] { background: #bfe3ff; color: #0b2233; }
.detail__type[data-type='shared'] { background: #ffd9b8; color: #3a1d06; }
.detail__layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 24px; align-items: start; }
.detail__main { display: grid; gap: 20px; }
.detail__head { display: grid; gap: 8px; }
.detail__head h1 { font-size: clamp(22px, 2.8vw, 32px); font-weight: 900; line-height: 1.2; }
.detail__place { display: flex; align-items: center; gap: 6px; color: var(--ink-secondary); font-size: 14px; }
.detail__price { color: var(--ink-muted); font-weight: 700; }
.detail__price strong { margin-right: 2px; color: var(--ink); font-size: 30px; font-weight: 900; }
.detail__tags { display: flex; flex-wrap: wrap; gap: 6px; }
.detail__tags li { padding: 3px 10px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--acid-soft); color: var(--ink); font-size: 13px; font-weight: 700; }
.detail__facts { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.detail__facts div { padding: 12px; border: 1.5px solid var(--rule); border-radius: 12px; background: var(--paper-raised); }
.detail__facts dt { color: var(--ink-muted); font-size: 12px; font-weight: 700; }
.detail__facts dd { margin-top: 4px; font-size: 16px; font-weight: 850; }
.detail__section { display: grid; gap: 10px; }
.detail__section h2 { display: inline-flex; align-items: center; gap: 6px; font-size: 18px; font-weight: 900; font-style: italic; }
.detail__desc { color: var(--ink-secondary); line-height: 1.8; white-space: pre-line; }
.detail__busy { display: flex; flex-wrap: wrap; gap: 8px; }
.detail__busy li { padding: 4px 10px; border: 1.5px dashed var(--rule-strong); border-radius: 8px; color: var(--ink-secondary); font-size: 13px; }
.detail__map { height: 280px; border: 1.5px solid var(--rule-strong); border-radius: 14px; overflow: hidden; }
.detail__aside { position: sticky; top: 76px; display: grid; gap: 10px; }
.detail__landlord { color: var(--ink-secondary); font-size: 14px; font-weight: 700; }
@media (max-width: 960px) {
  .detail__layout { grid-template-columns: 1fr; }
  .detail__aside { position: static; }
}
</style>
