<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { Inquiry, Overview } from '@/features/console/types'
import type { BillsSummary } from '@/features/console/leasingTypes'
import { leasingApi } from '@/features/console/leasingApi'
import { yuan } from '@/features/console/money'

defineOptions({ name: 'LandlordOverview' })

const { t } = useI18n()
const overview = ref<Overview | null>(null)
const pending = ref<Inquiry[]>([])
const rent = ref<BillsSummary | null>(null)
const errorText = ref('')

onMounted(async () => {
  try {
    const [stats, inquiries, bills] = await Promise.all([
      landlordApi.overview(), landlordApi.inquiries({ status: 'new', pageSize: 5 }), leasingApi.billsSummary(),
    ])
    overview.value = stats
    pending.value = inquiries.items
    rent.value = bills
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  }
})
</script>

<template>
  <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
  <template v-else-if="overview">
    <div class="c-stats">
      <RouterLink :to="{ path: '/landlord/listings', query: { status: 'published' } }" class="c-stat">
        <strong>{{ overview.listings.published }}</strong><span>{{ t('console.status.published') }}</span>
      </RouterLink>
      <RouterLink :to="{ path: '/landlord/listings', query: { status: 'draft' } }" class="c-stat">
        <strong>{{ overview.listings.draft }}</strong><span>{{ t('console.status.draft') }}</span>
      </RouterLink>
      <RouterLink :to="{ path: '/landlord/listings', query: { status: 'offline' } }" class="c-stat">
        <strong>{{ overview.listings.offline }}</strong><span>{{ t('console.status.offline') }}</span>
      </RouterLink>
      <RouterLink to="/landlord/estates" class="c-stat"><strong>{{ overview.estates }}</strong><span>{{ t('console.tabs.estates') }}</span></RouterLink>
      <RouterLink :to="{ path: '/landlord/inquiries', query: { status: 'new' } }" class="c-stat">
        <strong>{{ overview.newInquiries }}</strong><span>{{ t('console.newInquiries') }}</span>
      </RouterLink>
      <div class="c-stat"><strong>{{ overview.weekInquiries }}</strong><span>{{ t('console.weekInquiries') }}</span></div>
      <RouterLink v-if="rent" :to="{ path: '/landlord/bills', query: { view: 'overdue' } }" class="c-stat">
        <strong :class="{ 'c-error': rent.overdueCount > 0 }">{{ yuan(rent.overdueAmount) }}</strong><span>{{ t('lease.summary.overdue', { n: rent.overdueCount }) }}</span>
      </RouterLink>
      <RouterLink v-if="rent" to="/landlord/bills" class="c-stat">
        <strong>{{ yuan(rent.monthOutstanding) }}</strong><span>{{ t('lease.summary.monthOutstanding') }}</span>
      </RouterLink>
    </div>

    <div class="c-toolbar">
      <RouterLink to="/landlord/listings/new" class="c-btn c-btn--primary"><Plus :size="16" aria-hidden="true" />{{ t('console.newListing') }}</RouterLink>
      <RouterLink to="/landlord/estates" class="c-btn">{{ t('console.manageEstates') }}</RouterLink>
    </div>

    <section class="c-card">
      <h2>{{ t('console.pendingInquiries') }}</h2>
      <p v-if="!pending.length" class="c-hint">{{ t('console.noPending') }}</p>
      <ul v-else class="pending">
        <li v-for="item in pending" :key="item.id">
          <strong>{{ item.name }} · {{ item.phone }}</strong>
          <span>{{ item.listingTitle }}</span>
          <span v-if="item.message" class="c-hint">{{ item.message }}</span>
        </li>
      </ul>
      <RouterLink v-if="pending.length" :to="{ path: '/landlord/inquiries', query: { status: 'new' } }" class="c-btn c-btn--sm">{{ t('home.viewAll') }}</RouterLink>
    </section>
  </template>
  <p v-else class="c-hint">{{ t('common.loading') }}</p>
</template>

<style scoped>
.pending { display: grid; gap: 10px; margin-bottom: 12px; }
.pending li { display: grid; gap: 2px; padding: 10px 12px; border: 1px solid var(--rule); border-radius: 10px; background: var(--paper); }
</style>
