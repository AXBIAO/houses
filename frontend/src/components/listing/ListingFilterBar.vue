<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RotateCcw, Search } from 'lucide-vue-next'
import StayPeriodPicker from './StayPeriodPicker.vue'
import { RENT_TYPES, SORT_KEYS, type Facets, type RentType, type SortKey } from '@/features/listings/types'
import { EMPTY_SEARCH, isFiltered, withChanges, type SearchState } from '@/features/listings/searchQuery'

interface PricePreset { min: number | null; max: number | null }

const MONTHLY_PRESETS: readonly PricePreset[] = [
  { min: null, max: 1500 }, { min: 1500, max: 3000 }, { min: 3000, max: 5000 }, { min: 5000, max: null },
]
const NIGHTLY_PRESETS: readonly PricePreset[] = [
  { min: null, max: 200 }, { min: 200, max: 400 }, { min: 400, max: null },
]
const BEDROOM_OPTIONS = [1, 2, 3] as const
const TAG_LIMIT = 12

const props = defineProps<{ modelValue: SearchState; facets: Facets | null; showSort?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: SearchState] }>()
const { t } = useI18n()

const keyword = ref(props.modelValue.q)
watch(() => props.modelValue.q, (q) => { keyword.value = q })

const state = computed(() => props.modelValue)
const presets = computed(() => (state.value.type === 'short' ? NIGHTLY_PRESETS : MONTHLY_PRESETS))
const tags = computed(() => {
  const fromFacets = props.facets?.tags.slice(0, TAG_LIMIT).map(f => f.value) ?? []
  // 链接里带来的标签即便不在热门里也要能看到并取消
  return [...new Set([...state.value.tags, ...fromFacets])]
})
const typeTabs: readonly (RentType | null)[] = [null, ...RENT_TYPES]

function update(changes: Partial<SearchState>) {
  emit('update:modelValue', withChanges(state.value, changes))
}
function pickType(type: RentType | null) {
  // 月价与晚价不可比，切换类型时清掉价格区间
  update({ type, minPrice: null, maxPrice: null })
}
function isPreset(p: PricePreset) {
  return state.value.minPrice === p.min && state.value.maxPrice === p.max
}
function pickPreset(p: PricePreset) {
  update(isPreset(p) ? { minPrice: null, maxPrice: null } : { minPrice: p.min, maxPrice: p.max })
}
function presetLabel(p: PricePreset) {
  if (p.min == null) return t('filters.priceUnder', { n: p.max })
  if (p.max == null) return t('filters.priceOver', { n: p.min })
  return `${p.min}–${p.max}`
}
function toggleTag(tag: string) {
  const current = state.value.tags
  update({ tags: current.includes(tag) ? current.filter(x => x !== tag) : [...current, tag].slice(0, 8) })
}
function reset() {
  emit('update:modelValue', withChanges(EMPTY_SEARCH, { sort: state.value.sort }))
}
</script>

<template>
  <section class="filters" :aria-label="t('filters.title')">
    <div class="filters__row filters__row--top">
      <div class="seg" role="tablist">
        <button
          v-for="type in typeTabs" :key="type ?? 'all'" type="button" role="tab" class="seg__item"
          :class="{ 'is-active': state.type === type }" :aria-selected="state.type === type" @click="pickType(type)"
        >{{ t(`rentType.${type ?? 'all'}`) }}</button>
      </div>
      <form class="filters__search" @submit.prevent="update({ q: keyword })">
        <Search :size="18" aria-hidden="true" />
        <input v-model="keyword" type="search" maxlength="100" :placeholder="t('filters.keyword')" :aria-label="t('filters.keyword')" />
        <button type="submit">{{ t('common.search') }}</button>
      </form>
    </div>

    <div class="filters__row">
      <span class="filters__label">{{ t('filters.district') }}</span>
      <select class="filters__select" :value="state.district" :aria-label="t('filters.district')" @change="update({ district: ($event.target as HTMLSelectElement).value })">
        <option value="">{{ t('rentType.all') }}</option>
        <option v-for="d in facets?.districts ?? []" :key="d.value" :value="d.value">{{ d.value }}（{{ d.count }}）</option>
      </select>
      <span class="filters__label">{{ state.type === 'short' ? t('filters.priceNight') : t('filters.priceMonth') }}</span>
      <button
        v-for="p in presets" :key="`${p.min}-${p.max}`" type="button" class="chip"
        :class="{ 'is-active': isPreset(p) }" :aria-pressed="isPreset(p)" @click="pickPreset(p)"
      >{{ presetLabel(p) }}</button>
    </div>

    <div class="filters__row">
      <span class="filters__label">{{ t('filters.bedrooms') }}</span>
      <button
        v-for="n in BEDROOM_OPTIONS" :key="n" type="button" class="chip"
        :class="{ 'is-active': state.bedrooms === n }" :aria-pressed="state.bedrooms === n"
        @click="update({ bedrooms: state.bedrooms === n ? null : n })"
      >{{ n === 3 ? t('filters.bedroomsPlus', { n }) : t('filters.bedroomsN', { n }) }}</button>
      <button
        type="button" class="chip" :class="{ 'is-active': state.recommended }" :aria-pressed="state.recommended"
        @click="update({ recommended: !state.recommended })"
      >{{ t('home.recommended') }}</button>
    </div>

    <StayPeriodPicker
      :rent-type="state.type"
      :move-in="state.moveIn" :move-out="state.moveOut" :months="state.months"
      @update:move-in="update({ moveIn: $event })" @update:move-out="update({ moveOut: $event })" @update:months="update({ months: $event })"
    />

    <div v-if="tags.length" class="filters__row">
      <span class="filters__label">{{ t('filters.tags') }}</span>
      <button
        v-for="tag in tags" :key="tag" type="button" class="chip"
        :class="{ 'is-active': state.tags.includes(tag) }" :aria-pressed="state.tags.includes(tag)" @click="toggleTag(tag)"
      >{{ tag }}</button>
    </div>

    <div class="filters__row filters__row--end">
      <label v-if="showSort !== false" class="filters__sort">{{ t('filters.sort') }}
        <select class="filters__select" :value="state.sort" @change="update({ sort: ($event.target as HTMLSelectElement).value as SortKey })">
          <option v-for="key in SORT_KEYS.filter(k => k !== 'distance')" :key="key" :value="key">{{ t(`filters.sortBy.${key}`) }}</option>
        </select>
      </label>
      <button v-if="isFiltered(state)" type="button" class="filters__reset" @click="reset">
        <RotateCcw :size="14" aria-hidden="true" />{{ t('common.reset') }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.filters { display: grid; gap: 12px; padding: 16px; border: 2px solid var(--rule-strong); border-radius: 16px; background: var(--paper-raised); box-shadow: 4px 4px 0 var(--shadow-hard); }
.filters__row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 10px; }
.filters__row--top { justify-content: space-between; }
.filters__row--end { justify-content: flex-end; }
.filters__label { margin-right: 2px; color: var(--ink-secondary); font-size: 13px; font-weight: 800; }
.seg { display: inline-flex; padding: 3px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper); }
.seg__item { height: 34px; padding: 0 16px; border-radius: 999px; color: var(--ink); font-size: 14px; font-weight: 800; cursor: pointer; }
.seg__item.is-active { background: var(--ink); color: var(--paper-raised); }
.filters__search { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 240px; max-width: 520px; height: 42px; padding: 0 4px 0 12px; border: 1.5px solid var(--rule-strong); border-radius: 12px; background: var(--paper); color: var(--ink-muted); }
.filters__search input { flex: 1; min-width: 0; border: 0; background: transparent; color: var(--ink); font-size: 15px; outline: none; }
.filters__search button { height: 34px; padding: 0 14px; border: 1.5px solid var(--rule-strong); border-radius: 9px; background: var(--acid); color: var(--acid-ink); font-weight: 800; }
.filters__select { height: 34px; padding: 0 8px; border: 1.5px solid var(--rule-strong); border-radius: 8px; background: var(--paper); color: var(--ink); font-size: 13px; }
.filters__sort { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-secondary); font-size: 13px; font-weight: 700; }
.filters__reset { display: inline-flex; align-items: center; gap: 4px; height: 34px; padding: 0 12px; color: var(--ink-secondary); font-size: 13px; font-weight: 700; text-decoration: underline; }
.chip { height: 32px; padding: 0 12px; border: 1.5px solid var(--rule); border-radius: 999px; background: var(--paper); color: var(--ink-secondary); font-size: 13px; font-weight: 700; cursor: pointer; }
.chip.is-active { border-color: var(--rule-strong); background: var(--acid); color: var(--acid-ink); }
@media (max-width: 640px) {
  .filters { padding: 12px; }
  .filters__search { min-width: 100%; }
}
</style>
