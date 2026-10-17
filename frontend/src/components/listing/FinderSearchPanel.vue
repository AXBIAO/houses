<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Search, Sparkles } from 'lucide-vue-next'
import StayPeriodPicker from './StayPeriodPicker.vue'
import { RENT_TYPES, type RentType } from '@/features/listings/types'
import { EMPTY_SEARCH, toQuery, withChanges, type SearchState } from '@/features/listings/searchQuery'

defineProps<{ tags: readonly string[] }>()
const emit = defineEmits<{ typeChange: [type: RentType | null] }>()
const { t } = useI18n()
const router = useRouter()

const TABS: readonly (RentType | null)[] = [null, ...RENT_TYPES]
const state = reactive<SearchState>(withChanges(EMPTY_SEARCH, {}))

function pickType(type: RentType | null) {
  state.type = type
  emit('typeChange', type)
}
function toggleTag(tag: string) {
  state.tags = state.tags.includes(tag) ? state.tags.filter(x => x !== tag) : [...state.tags, tag]
}
function search() {
  void router.push({ path: '/listings', query: toQuery(state) })
}
function aiSearch() {
  void router.push({ path: '/ai', query: toQuery(state) })
}
</script>

<template>
  <section class="finder" :aria-label="t('common.search')">
    <div class="finder__tabs" role="tablist">
      <button
        v-for="type in TABS" :key="type ?? 'all'" type="button" role="tab"
        class="finder__tab" :class="{ 'is-active': state.type === type }" :aria-selected="state.type === type"
        @click="pickType(type)"
      >{{ t(`rentType.${type ?? 'all'}`) }}</button>
    </div>

    <form class="finder__box" @submit.prevent="search">
      <Search class="finder__icon" :size="20" aria-hidden="true" />
      <input v-model="state.q" class="finder__input" type="search" :placeholder="t('home.searchPlaceholder')" :aria-label="t('home.searchPlaceholder')" maxlength="100" />
      <button type="submit" class="finder__btn finder__btn--search">{{ t('home.searchButton') }}</button>
      <button type="button" class="finder__btn finder__btn--ai" @click="aiSearch">
        <Sparkles :size="16" aria-hidden="true" />{{ t('home.aiButton') }}
      </button>
    </form>

    <StayPeriodPicker v-model:move-in="state.moveIn" v-model:move-out="state.moveOut" v-model:months="state.months" :rent-type="state.type" />

    <div v-if="tags.length" class="finder__tags">
      <span class="finder__label">{{ t('home.quickFilters') }}</span>
      <button
        v-for="tag in tags" :key="tag" type="button" class="finder__chip"
        :class="{ 'is-active': state.tags.includes(tag) }" :aria-pressed="state.tags.includes(tag)" @click="toggleTag(tag)"
      >{{ tag }}</button>
    </div>
  </section>
</template>

<style scoped>
.finder { display: grid; gap: 14px; padding: 18px; border: 2px solid var(--rule-strong); border-radius: 18px; background: var(--paper-raised); box-shadow: 5px 5px 0 var(--shadow-hard); }
.finder__tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.finder__tab { min-width: 72px; height: 38px; padding: 0 16px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper); color: var(--ink); font-size: 14px; font-weight: 800; cursor: pointer; }
.finder__tab.is-active { background: var(--ink); color: var(--paper-raised); }
.finder__box { display: flex; align-items: center; gap: 8px; padding: 6px 6px 6px 14px; border: 2px solid var(--rule-strong); border-radius: 14px; background: var(--paper); }
.finder__icon { flex: none; color: var(--ink-muted); }
.finder__input { flex: 1; min-width: 0; height: 44px; border: 0; background: transparent; color: var(--ink); font-size: 16px; outline: none; }
.finder__btn { display: inline-flex; align-items: center; gap: 6px; flex: none; height: 44px; padding: 0 18px; border: 2px solid var(--rule-strong); border-radius: 10px; font-size: 15px; font-weight: 850; cursor: pointer; white-space: nowrap; }
.finder__btn--search { background: var(--paper-raised); color: var(--ink); }
.finder__btn--ai { background: var(--acid); color: var(--acid-ink); box-shadow: 2px 2px 0 var(--shadow-hard); }
.finder__btn:hover { transform: translateY(-1px); }
.finder__tags { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 10px; }
.finder__label { margin-right: 4px; color: var(--ink-secondary); font-size: 13px; font-weight: 800; }
.finder__chip { height: 32px; padding: 0 12px; border: 1.5px solid var(--rule); border-radius: 999px; background: var(--paper); color: var(--ink-secondary); font-size: 13px; font-weight: 700; cursor: pointer; }
.finder__chip.is-active { border-color: var(--rule-strong); background: var(--acid); color: var(--acid-ink); }
@media (max-width: 640px) {
  .finder { padding: 14px; }
  .finder__box { flex-wrap: wrap; padding: 8px; }
  .finder__input { flex-basis: calc(100% - 40px); }
  .finder__btn { flex: 1; justify-content: center; }
}
</style>
