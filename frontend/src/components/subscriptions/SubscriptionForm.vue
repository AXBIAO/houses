<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ListingFilterBar from '@/components/listing/ListingFilterBar.vue'
import { parseSearch, toQuery, withChanges, type SearchState } from '@/features/listings/searchQuery'
import { useFacets } from '@/features/listings/useFacets'
import { describeFilters } from '@/features/subscriptions/describe'
import type { Subscription, SubscriptionInput } from '@/features/subscriptions/api'
import '@/console.css'

/** 订阅条件就是找房条件：直接复用列表页的筛选栏，保存为 /api/listings 参数。 */
const props = defineProps<{ initial: Subscription | null; initialFilters: Record<string, string>; emailAvailable: boolean; saving: boolean; errorText: string }>()
const emit = defineEmits<{ submit: [input: SubscriptionInput]; cancel: [] }>()
const { t } = useI18n()
const facets = useFacets()

const search = ref<SearchState>(withChanges(parseSearch(props.initial?.filters ?? props.initialFilters), { sort: 'latest', recommended: false }))
const name = ref(props.initial?.name ?? '')
const emailEnabled = ref(props.initial?.emailEnabled ?? false)
const localError = ref('')

const filters = computed(() => {
  const { sort: _sort, recommended: _rec, ...rest } = toQuery(search.value)
  return rest
})
const labels = computed(() => describeFilters(filters.value, t))
const suggestedName = computed(() => labels.value.slice(0, 3).join(' · '))

function submit() {
  localError.value = ''
  if (!labels.value.length) {
    localError.value = t('subs.needCondition')
    return
  }
  const finalName = (name.value.trim() || suggestedName.value).slice(0, 30)
  emit('submit', { name: finalName, filters: filters.value, emailEnabled: emailEnabled.value, active: props.initial?.active ?? true })
}
</script>

<template>
  <!-- 外层不能用 form：筛选栏里自带搜索表单，嵌套 form 会让「搜索」误提交订阅 -->
  <section class="c-card sub-form">
    <h2>{{ initial ? t('subs.edit') : t('subs.create') }}</h2>
    <ListingFilterBar v-model="search" :facets="facets" :show-sort="false" />
    <p class="c-hint">{{ labels.length ? t('subs.willNotify', { conditions: labels.join('、') }) : t('subs.needCondition') }}</p>
    <div class="c-form-grid">
      <label class="c-field">{{ t('subs.name') }}<input v-model="name" class="c-input" maxlength="30" :placeholder="suggestedName || t('subs.namePlaceholder')" /></label>
      <label class="c-field">{{ t('subs.channels') }}
        <span class="check"><input v-model="emailEnabled" type="checkbox" :disabled="!emailAvailable" /> {{ t('subs.email') }}</span>
        <span v-if="!emailAvailable" class="c-hint">{{ t('subs.emailUnavailable') }}</span>
      </label>
    </div>
    <p v-if="localError || errorText" class="c-error" role="alert">{{ localError || errorText }}</p>
    <div class="c-toolbar actions">
      <button type="button" class="c-btn" @click="emit('cancel')">{{ t('common.cancel') }}</button>
      <button type="button" class="c-btn c-btn--primary sub-form__submit" :disabled="saving" @click="submit">{{ initial ? t('console.save') : t('subs.create') }}</button>
    </div>
  </section>
</template>

<style scoped>
.sub-form { display: grid; gap: 14px; }
.sub-form > h2 { margin: 0; }
.sub-form :deep(.filters) { box-shadow: none; }
.check { display: inline-flex; align-items: center; gap: 6px; min-height: 38px; color: var(--ink); font-weight: 700; }
.actions { justify-content: flex-end; }
</style>
