<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Phone } from 'lucide-vue-next'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { Inquiry, InquiryStatus } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LandlordInquiries' })

const PAGE_SIZE = 20
const STATUSES: readonly InquiryStatus[] = ['new', 'contacted', 'closed']
const TONES: Record<InquiryStatus, string> = { new: 'warn', contacted: 'good', closed: 'muted' }

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const items = ref<Inquiry[]>([])
const total = ref(0)
const loading = ref(false)
const notes = ref<Record<number, string>>({})

const status = computed(() => (STATUSES as readonly string[]).includes(String(route.query.status)) ? String(route.query.status) as InquiryStatus : null)
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function setQuery(changes: Record<string, string | undefined>) {
  const query = { ...route.query, ...changes }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  void router.replace({ query })
}

async function load() {
  loading.value = true
  try {
    const res = await landlordApi.inquiries({ status: status.value ?? undefined, page: page.value, pageSize: PAGE_SIZE })
    items.value = res.items
    total.value = res.total
    notes.value = Object.fromEntries(res.items.map(i => [i.id, i.note]))
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

async function update(item: Inquiry, next: InquiryStatus) {
  try {
    const saved = await landlordApi.updateInquiry(item.id, { status: next, note: notes.value[item.id] ?? '' })
    items.value = items.value.map(i => (i.id === saved.id ? saved : i))
    showToast(t('console.saved'))
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

const formatTime = (iso: string) => new Date(iso).toLocaleString()

watch(() => [status.value, page.value], load, { immediate: true })
</script>

<template>
  <div class="c-toolbar">
    <button type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': !status }" @click="setQuery({ status: undefined, page: undefined })">{{ t('rentType.all') }}</button>
    <button
      v-for="s in STATUSES" :key="s" type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': status === s }"
      @click="setQuery({ status: s, page: undefined })"
    >{{ t(`console.inquiryStatus.${s}`) }}</button>
  </div>

  <p v-if="loading && !items.length" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!items.length" class="c-empty"><p>{{ t('console.noInquiries') }}</p></div>
  <ul v-else class="inquiries">
    <li v-for="item in items" :key="item.id" class="c-card inquiry">
      <header class="inquiry__head">
        <strong>{{ item.name }}</strong>
        <a :href="`tel:${item.phone}`" class="inquiry__phone"><Phone :size="14" aria-hidden="true" />{{ item.phone }}</a>
        <span class="c-badge" :data-tone="TONES[item.status]">{{ t(`console.inquiryStatus.${item.status}`) }}</span>
        <span class="c-hint inquiry__time">{{ formatTime(item.createdAt) }}</span>
      </header>
      <p>
        <RouterLink :to="`/landlord/listings/${item.listingId}`" class="inquiry__listing">{{ item.listingTitle }}</RouterLink>
        <span v-if="item.moveIn" class="c-hint"> · {{ t('console.wantsMoveIn', { date: item.moveIn }) }}<template v-if="item.moveOut"> → {{ item.moveOut }}</template></span>
      </p>
      <p v-if="item.message" class="inquiry__message">{{ item.message }}</p>
      <div class="inquiry__follow">
        <input v-model="notes[item.id]" class="c-input" maxlength="500" :placeholder="t('console.notePlaceholder')" :aria-label="t('console.note')" />
        <button v-if="item.status !== 'contacted'" type="button" class="c-btn c-btn--sm c-btn--primary" @click="update(item, 'contacted')">{{ t('console.markContacted') }}</button>
        <button v-if="item.status !== 'closed'" type="button" class="c-btn c-btn--sm" @click="update(item, 'closed')">{{ t('console.markClosed') }}</button>
        <button v-if="item.status !== 'new'" type="button" class="c-btn c-btn--sm" @click="update(item, 'new')">{{ t('console.markNew') }}</button>
        <RouterLink v-if="item.status !== 'closed'" :to="{ path: '/landlord/leases/new', query: { listingId: item.listingId, inquiryId: item.id } }" class="c-btn c-btn--sm">{{ t('lease.signFromInquiry') }}</RouterLink>
      </div>
    </li>
  </ul>

  <div v-if="pages > 1" class="c-pager">
    <button type="button" class="c-btn c-btn--sm" :disabled="page <= 1" @click="setQuery({ page: String(page - 1) })">{{ t('console.prev') }}</button>
    <span>{{ page }} / {{ pages }}</span>
    <button type="button" class="c-btn c-btn--sm" :disabled="page >= pages" @click="setQuery({ page: String(page + 1) })">{{ t('console.next') }}</button>
  </div>
</template>

<style scoped>
.inquiries { display: grid; gap: 12px; }
.inquiry { display: grid; gap: 8px; box-shadow: none; }
.inquiry__head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.inquiry__phone { display: inline-flex; align-items: center; gap: 4px; font-weight: 800; text-decoration: underline; }
.inquiry__time { margin-left: auto; }
.inquiry__listing { font-weight: 700; }
.inquiry__listing:hover { text-decoration: underline; }
.inquiry__message { padding: 8px 10px; border-radius: 8px; background: var(--paper); color: var(--ink-secondary); white-space: pre-line; }
.inquiry__follow { display: flex; flex-wrap: wrap; gap: 8px; }
.inquiry__follow .c-input { flex: 1; min-width: 200px; }
</style>
