<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { BellPlus, List, LocateFixed, Sparkles, X } from 'lucide-vue-next'
import ListingCard from '@/components/listing/ListingCard.vue'
import ListingGridSkeleton from '@/components/listing/ListingGridSkeleton.vue'
import { listingsApi } from '@/features/listings/api'
import { locateUser, type LatLng } from '@/features/listings/geo'
import { aiApi, type AiCondition, type AiResult } from '@/features/subscriptions/api'
import { subscribableFilters, withoutCondition } from '@/features/subscriptions/aiFilters'
import type { ListingSummary } from '@/features/listings/types'
import { errorMessage } from '@/features/console/errors'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'AiSearchView' })

const EXAMPLES = [
  'ai.examples.long', 'ai.examples.short', 'ai.examples.shared', 'ai.examples.near',
] as const

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const text = ref(String(route.query.q ?? ''))
const result = ref<AiResult | null>(null)
const conditions = ref<AiCondition[]>([])
const filters = ref<Record<string, string>>({})
const items = ref<(ListingSummary & { reasons?: string[] })[]>([])
const total = ref(0)
const loading = ref(false)
const errorText = ref('')
const position = ref<LatLng | null>(null)

const listQuery = computed(() => filters.value)
const subscribeQuery = computed(() => ({ new: '1', ...subscribableFilters(filters.value) }))

async function run(query = text.value) {
  const value = query.trim()
  if (!value) return
  text.value = value
  loading.value = true
  errorText.value = ''
  void router.replace({ query: { q: value } })
  try {
    const res = await aiApi.search(value, position.value)
    result.value = res
    conditions.value = res.conditions
    filters.value = res.filters
    items.value = res.items
    total.value = res.total
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    loading.value = false
  }
}

async function removeCondition(condition: AiCondition) {
  filters.value = withoutCondition(filters.value, condition.key)
  conditions.value = conditions.value.filter(c => c.key !== condition.key)
  loading.value = true
  try {
    const page = await listingsApi.search({ ...filters.value, pageSize: 12 })
    items.value = page.items
    total.value = page.total
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

async function useLocation() {
  try {
    position.value = await locateUser()
    await run()
  } catch {
    showToast(t('home.locateFailed'))
  }
}

onMounted(() => {
  if (text.value) void run()
})
</script>

<template>
  <div class="ai">
    <section class="ai__hero">
      <h1><Sparkles :size="30" aria-hidden="true" />{{ t('navigation.ai') }}</h1>
      <p>{{ t('ai.lead') }}</p>
      <form class="ai__box" @submit.prevent="run()">
        <textarea
          v-model="text" class="ai__input" rows="2" maxlength="200" :placeholder="t('ai.placeholder')" :aria-label="t('ai.placeholder')"
          @keydown.enter.exact.prevent="run()"
        />
        <button type="submit" class="ai__go" :disabled="loading || !text.trim()"><Sparkles :size="18" aria-hidden="true" />{{ loading ? t('ai.thinking') : t('home.aiButton') }}</button>
      </form>
      <div class="ai__examples">
        <span class="c-hint">{{ t('ai.tryThese') }}</span>
        <button v-for="key in EXAMPLES" :key="key" type="button" class="ai__example" @click="run(t(key))">{{ t(key) }}</button>
      </div>
    </section>

    <p v-if="errorText" class="ai__error" role="alert">{{ errorText }}</p>

    <section v-if="result" class="ai__understood">
      <header class="ai__understood-head">
        <h2>{{ t('ai.understood') }}</h2>
        <span class="ai__source" :data-source="result.source">{{ result.source === 'llm' ? t('ai.sourceLlm') : t('ai.sourceRules') }}</span>
      </header>
      <p v-if="!result.understood" class="c-hint">{{ t('ai.notUnderstood') }}</p>
      <ul v-else class="ai__chips">
        <li v-for="c in conditions" :key="c.key">
          {{ c.label }}
          <button type="button" :aria-label="t('ai.removeCondition', { label: c.label })" @click="removeCondition(c)"><X :size="12" aria-hidden="true" /></button>
        </li>
      </ul>
      <p v-if="result.relaxed.length" class="ai__relaxed">{{ t('ai.relaxed', { items: result.relaxed.join('、') }) }}</p>
      <button v-if="result.needLocation" type="button" class="pill-btn" @click="useLocation"><LocateFixed :size="16" aria-hidden="true" />{{ t('home.locateMe') }}</button>
      <div class="ai__actions">
        <span class="ai__count">{{ t('listing.found', { n: total }) }}</span>
        <RouterLink :to="{ path: '/listings', query: listQuery }" class="pill-btn"><List :size="16" aria-hidden="true" />{{ t('ai.viewList') }}</RouterLink>
        <RouterLink :to="{ path: '/subscriptions', query: subscribeQuery }" class="pill-btn pill-btn--acid"><BellPlus :size="16" aria-hidden="true" />{{ t('ai.subscribe') }}</RouterLink>
      </div>
    </section>

    <ListingGridSkeleton v-if="loading && !items.length" :count="6" />
    <div v-else-if="items.length" class="card-grid">
      <div v-for="item in items" :key="item.id" class="ai__result">
        <ListingCard :listing="item" />
        <ul v-if="item.reasons?.length" class="ai__reasons">
          <li v-for="r in item.reasons" :key="r">✓ {{ r }}</li>
        </ul>
      </div>
    </div>
    <div v-else-if="result" class="ai__empty">
      <p>{{ t('ai.empty') }}</p>
      <RouterLink :to="{ path: '/subscriptions', query: subscribeQuery }" class="pill-btn pill-btn--acid">{{ t('ai.subscribe') }}</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.ai { display: grid; gap: 22px; }
.ai__hero { display: grid; gap: 12px; }
.ai__hero h1 { display: inline-flex; align-items: center; gap: 10px; font-size: clamp(30px, 4.5vw, 48px); font-weight: 900; }
.ai__hero > p { color: var(--ink-secondary); font-size: 16px; }
.ai__box { display: flex; align-items: stretch; gap: 10px; padding: 10px; border: 2px solid var(--rule-strong); border-radius: 18px; background: var(--paper-raised); box-shadow: 5px 5px 0 var(--shadow-hard); }
.ai__input { flex: 1; min-width: 0; padding: 8px 10px; border: 0; background: transparent; color: var(--ink); font: inherit; font-size: 17px; line-height: 1.5; resize: none; outline: none; }
.ai__go { display: inline-flex; align-items: center; gap: 6px; padding: 0 20px; border: 2px solid var(--rule-strong); border-radius: 12px; background: var(--acid); color: var(--acid-ink); font-size: 16px; font-weight: 900; white-space: nowrap; cursor: pointer; }
.ai__go:disabled { opacity: .6; cursor: progress; }
.ai__examples { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.ai__example { padding: 6px 12px; border: 1.5px dashed var(--rule-strong); border-radius: 999px; background: var(--paper); color: var(--ink-secondary); font-size: 13px; cursor: pointer; }
.ai__example:hover { border-style: solid; color: var(--ink); }
.ai__error { color: var(--danger, #c0392b); }
.ai__understood { display: grid; gap: 12px; padding: 16px 18px; border: 1.5px solid var(--rule-strong); border-radius: 16px; background: var(--paper-raised); }
.ai__understood-head { display: flex; align-items: center; gap: 10px; }
.ai__understood-head h2 { font-size: 18px; font-weight: 900; }
.ai__source { padding: 2px 10px; border: 1.5px solid var(--rule-strong); border-radius: 999px; font-size: 12px; font-weight: 800; }
.ai__source[data-source='llm'] { background: var(--acid); color: var(--acid-ink); }
.ai__chips { display: flex; flex-wrap: wrap; gap: 8px; }
.ai__chips li { display: inline-flex; align-items: center; gap: 6px; padding: 4px 6px 4px 12px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--acid-soft); color: var(--ink); font-size: 14px; font-weight: 800; }
:root[data-theme='dark'] .ai__chips li { background: var(--paper-muted); }
.ai__chips button { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; }
.ai__chips button:hover { background: var(--paper-raised); }
.ai__relaxed { color: var(--ink-secondary); font-size: 13px; }
.ai__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.ai__count { margin-right: auto; font-weight: 800; }
.pill-btn { display: inline-flex; align-items: center; gap: 6px; height: 38px; padding: 0 16px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--paper-raised); color: var(--ink); font-size: 14px; font-weight: 800; cursor: pointer; width: fit-content; }
.pill-btn--acid { background: var(--acid); color: var(--acid-ink); box-shadow: 2px 2px 0 var(--shadow-hard); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 18px; }
.ai__result { display: grid; align-content: start; gap: 8px; }
.ai__reasons { display: flex; flex-wrap: wrap; gap: 4px 10px; padding: 0 4px; color: var(--ink-secondary); font-size: 12px; font-weight: 700; }
.ai__empty { display: grid; justify-items: center; gap: 12px; padding: 40px 16px; border: 1.5px dashed var(--rule-strong); border-radius: 16px; color: var(--ink-secondary); }
@media (max-width: 640px) {
  .ai__box { flex-direction: column; }
  .ai__go { justify-content: center; height: 44px; }
}
</style>
