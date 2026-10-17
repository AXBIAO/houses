<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MapPin } from 'lucide-vue-next'
import type { ListingSummary } from '@/features/listings/types'

const props = defineProps<{ listing: ListingSummary; distanceKm?: number | null }>()
const distance = computed(() => props.distanceKm ?? props.listing.distanceKm ?? null)
const { t } = useI18n()

const priceUnit = computed(() => t(props.listing.rentType === 'short' ? 'common.perNight' : 'common.perMonth'))
const layout = computed(() => {
  const { bedrooms, halls } = props.listing
  return props.listing.rentType === 'shared' ? t('listing.sharedRoom', { n: bedrooms }) : t('listing.layout', { rooms: bedrooms, halls })
})
const coverStyle = computed(() => {
  if (props.listing.coverUrl) return { backgroundImage: `url(${JSON.stringify(props.listing.coverUrl)})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  const h = (props.listing.id * 47) % 360
  return { background: `linear-gradient(135deg, hsl(${h} 70% 82%), hsl(${(h + 40) % 360} 65% 66%))` }
})
const freshness = computed(() => {
  const minutes = Math.max(1, Math.round((Date.now() - Date.parse(props.listing.publishedAt)) / 60_000))
  if (minutes < 60) return t('listing.minutesAgo', { n: minutes })
  if (minutes < 1440) return t('listing.hoursAgo', { n: Math.round(minutes / 60) })
  return t('listing.daysAgo', { n: Math.round(minutes / 1440) })
})
</script>

<template>
  <article class="listing-card">
    <RouterLink :to="`/listings/${listing.id}`" class="listing-card__link" :aria-label="listing.title">
      <div class="listing-card__cover" :style="coverStyle">
        <svg v-if="!listing.coverUrl" class="listing-card__art" viewBox="0 0 120 80" aria-hidden="true">
          <path d="M18 44 60 14l42 30" fill="none" stroke="currentColor" stroke-width="5" stroke-linejoin="round" stroke-linecap="round" />
          <path d="M28 40v30h64V40" fill="none" stroke="currentColor" stroke-width="5" stroke-linejoin="round" />
          <rect x="52" y="50" width="16" height="20" rx="2" fill="currentColor" />
          <rect x="35" y="46" width="11" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="3" />
          <rect x="74" y="46" width="11" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="3" />
        </svg>
        <span class="listing-card__type" :data-type="listing.rentType">{{ t(`rentType.${listing.rentType}`) }}</span>
        <span class="listing-card__fresh">{{ freshness }}</span>
      </div>
      <div class="listing-card__body">
        <p class="listing-card__price"><strong>¥{{ listing.price.toLocaleString() }}</strong><span>{{ priceUnit }}</span></p>
        <h3 class="listing-card__title">{{ listing.title }}</h3>
        <p class="listing-card__meta">
          <span>{{ layout }}</span><span aria-hidden="true">·</span>
          <span>{{ t('listing.area', { n: listing.area }) }}</span><span aria-hidden="true">·</span>
          <span>{{ listing.floor != null ? t('listing.floor', { n: listing.floor }) : '' }}</span>
        </p>
        <p class="listing-card__place">
          <MapPin :size="14" aria-hidden="true" />
          <span>{{ listing.district }} · {{ listing.community }}</span>
          <span v-if="distance != null" class="listing-card__distance">{{ t('listing.distance', { n: distance.toFixed(1) }) }}</span>
        </p>
        <ul class="listing-card__tags">
          <li v-for="tag in listing.tags" :key="tag">{{ tag }}</li>
        </ul>
      </div>
    </RouterLink>
  </article>
</template>

<style scoped>
.listing-card {
  border: 1.5px solid var(--rule-strong); border-radius: 14px; overflow: hidden;
  background: var(--paper-raised); box-shadow: 3px 3px 0 var(--shadow-hard);
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.listing-card:hover { transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--shadow-hard); }
.listing-card__link { display: flex; flex-direction: column; height: 100%; color: inherit; text-decoration: none; }
.listing-card__cover { position: relative; display: grid; place-items: center; aspect-ratio: 16 / 10; border-bottom: 1.5px solid var(--rule-strong); color: rgb(21 21 18 / .72); }
.listing-card__art { width: 46%; max-width: 140px; }
.listing-card__type, .listing-card__fresh {
  position: absolute; top: 10px; padding: 3px 9px; border: 1.5px solid var(--rule-strong); border-radius: 999px;
  font-size: 12px; font-weight: 800; line-height: 1.4;
}
.listing-card__type { left: 10px; background: var(--acid); color: var(--acid-ink); }
.listing-card__type[data-type='short'] { background: #bfe3ff; color: #0b2233; }
.listing-card__type[data-type='shared'] { background: #ffd9b8; color: #3a1d06; }
.listing-card__fresh { right: 10px; background: var(--paper-raised); color: var(--ink); font-weight: 700; }
.listing-card__body { display: grid; gap: 6px; padding: 14px 14px 16px; }
.listing-card__price { display: flex; align-items: baseline; gap: 2px; color: var(--ink); }
.listing-card__price strong { font-size: 22px; font-weight: 900; letter-spacing: -.02em; }
.listing-card__price span { color: var(--ink-muted); font-size: 13px; font-weight: 600; }
.listing-card__title { font-size: 15px; font-weight: 800; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.listing-card__meta, .listing-card__place { display: flex; align-items: center; gap: 6px; color: var(--ink-secondary); font-size: 13px; }
.listing-card__place { color: var(--ink-muted); }
.listing-card__distance { margin-left: auto; color: var(--ink); font-weight: 700; }
.listing-card__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.listing-card__tags li { padding: 2px 8px; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink-secondary); font-size: 12px; }
@media (prefers-reduced-motion: reduce) { .listing-card, .listing-card:hover { transition: none; transform: none; } }
</style>
