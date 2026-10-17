<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BillDialog from '@/components/console/BillDialog.vue'
import CheckoutDialog from '@/components/console/CheckoutDialog.vue'
import LeasingBadge from '@/components/console/LeasingBadge.vue'
import MeterForm from '@/components/console/MeterForm.vue'
import { leasingApi } from '@/features/console/leasingApi'
import type { BillSummary, FeeItem, LeaseDetail, MeterReading } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { todayIso, yuan } from '@/features/console/money'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LeaseDetail' })

const { t } = useI18n()
const route = useRoute()
const leaseId = Number(route.params.id)
const lease = ref<LeaseDetail | null>(null)
const feeItems = ref<FeeItem[]>([])
const errorText = ref('')
const billOpen = ref(false)
const billId = ref<number | null>(null)
const checkoutOpen = ref(false)

const open = computed(() => lease.value !== null && ['pending', 'active', 'expired'].includes(lease.value.status))
const canMeter = computed(() => lease.value !== null && ['active', 'expired'].includes(lease.value.status))
const metered = computed(() => feeItems.value.filter(f => f.kind === 'metered' && f.active))
const today = todayIso()

async function load() {
  try {
    const [l, f] = await Promise.all([leasingApi.lease(leaseId), leasingApi.feeItems()])
    lease.value = l
    feeItems.value = f.items
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  }
}

function openBill(bill: BillSummary) {
  billId.value = bill.id
  billOpen.value = true
}

async function voidLease() {
  if (!window.confirm(t('lease.confirmVoid'))) return
  try {
    lease.value = await leasingApi.voidLease(leaseId)
    showToast(t('lease.voidedLease'))
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function removeReading(r: MeterReading) {
  if (!window.confirm(t('lease.confirmDeleteReading'))) return
  try {
    await leasingApi.deleteReading(r.id)
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

const isOverdue = (b: BillSummary) => (b.status === 'unpaid' || b.status === 'partial') && b.dueDate < today
const outstandingOf = (b: BillSummary) => Math.max(0, b.totalAmount - b.discountAmount - b.paidAmount)

onMounted(load)
</script>

<template>
  <div class="c-toolbar">
    <RouterLink to="/landlord/leases" class="c-btn c-btn--sm">← {{ t('console.tabs.leases') }}</RouterLink>
  </div>
  <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
  <p v-else-if="!lease" class="c-hint">{{ t('common.loading') }}</p>
  <template v-else>
    <section class="c-card head">
      <div class="head__title">
        <h2>{{ lease.leaseNo }}</h2>
        <LeasingBadge :lease="lease.status" />
        <span class="c-toolbar__spacer" />
        <button v-if="lease.status === 'active' || lease.status === 'expired'" type="button" class="c-btn c-btn--primary" @click="checkoutOpen = true">{{ t('lease.checkout') }}</button>
        <button v-if="open" type="button" class="c-btn c-btn--danger" @click="voidLease">{{ t('lease.voidLease') }}</button>
      </div>
      <dl class="facts">
        <div><dt>{{ t('console.col.listing') }}</dt><dd><RouterLink :to="`/landlord/listings/${lease.listingId}`" class="link">{{ lease.listingTitle }}</RouterLink></dd></div>
        <div><dt>{{ t('lease.renter') }}</dt><dd>{{ lease.renterName }} · {{ lease.renterPhone }}<template v-if="lease.idCardTail"> · ****{{ lease.idCardTail }}</template></dd></div>
        <div><dt>{{ t('lease.term') }}</dt><dd>{{ lease.startDate }} ~ {{ lease.endDate }}</dd></div>
        <div><dt>{{ t('lease.monthlyRent') }}</dt><dd>{{ yuan(lease.monthlyRent) }} · {{ t(`lease.cycles.${lease.payCycleMonths}`) }}</dd></div>
        <div><dt>{{ t('lease.deposit') }}</dt><dd>{{ yuan(lease.deposit) }}</dd></div>
        <div><dt>{{ t('lease.outstanding') }}</dt><dd :class="{ 'c-error': lease.overdue > 0 }">{{ yuan(lease.outstanding) }}</dd></div>
        <div v-if="lease.fees.length" class="facts__wide"><dt>{{ t('lease.stepFees') }}</dt><dd>{{ lease.fees.map(f => `${f.name} ${f.price}`).join('，') }}</dd></div>
        <div v-if="lease.status === 'checked_out'" class="facts__wide">
          <dt>{{ t('lease.checkoutInfo') }}</dt>
          <dd>{{ lease.checkoutDate }} · {{ t('lease.result.offset', { amount: yuan(lease.depositOffset) }) }} · {{ t('lease.result.refund', { amount: yuan(lease.depositRefund) }) }}<template v-if="lease.checkoutNote"> · {{ lease.checkoutNote }}</template></dd>
        </div>
        <div v-if="lease.note" class="facts__wide"><dt>{{ t('lease.note') }}</dt><dd>{{ lease.note }}</dd></div>
      </dl>
    </section>

    <section class="c-card">
      <h2>{{ t('lease.bills') }}</h2>
      <p class="c-hint">{{ t('lease.recordOnly') }}</p>
      <div class="c-table-wrap">
        <table class="c-table">
          <thead>
            <tr><th>{{ t('lease.billKindCol') }}</th><th>{{ t('lease.period') }}</th><th>{{ t('lease.dueDate') }}</th><th>{{ t('lease.total') }}</th><th>{{ t('lease.paidAmount') }}</th><th>{{ t('lease.outstanding') }}</th><th>{{ t('console.col.status') }}</th><th /></tr>
          </thead>
          <tbody>
            <tr v-for="b in lease.bills" :key="b.id" :class="{ muted: b.status === 'void' }">
              <td>{{ b.kind === 'rent' ? t('lease.periodN', { n: b.periodNo }) : t(`lease.billKind.${b.kind}`) }}</td>
              <td>{{ b.periodStart ? `${b.periodStart} ~ ${b.periodEnd}` : '—' }}</td>
              <td>{{ b.dueDate }}</td>
              <td>
                {{ yuan(b.totalAmount) }}
                <!-- 退租后押金账单的「减免」是记账上的平衡项，对房东展示为应退押金 -->
                <p v-if="b.kind === 'deposit' && lease.status === 'checked_out'" class="c-hint">{{ t('lease.result.refund', { amount: yuan(lease.depositRefund) }) }}</p>
                <p v-else-if="b.discountAmount > 0" class="c-hint">{{ t('lease.discountN', { amount: yuan(b.discountAmount) }) }}</p>
              </td>
              <td>{{ yuan(b.paidAmount) }}</td>
              <td>{{ b.status === 'void' ? '—' : yuan(outstandingOf(b)) }}</td>
              <td><LeasingBadge :bill="b.status" :overdue="isOverdue(b)" /></td>
              <td class="c-actions">
                <button type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': outstandingOf(b) > 0 && b.status !== 'void' }" @click="openBill(b)">
                  {{ outstandingOf(b) > 0 && b.status !== 'void' ? t('lease.recordPayment') : t('lease.view') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="c-card">
      <h2>{{ t('lease.meters') }}</h2>
      <MeterForm v-if="canMeter && metered.length" :lease-id="lease.id" :metered-items="metered" :lease-fees="lease.fees" @saved="load" />
      <p v-else-if="canMeter" class="c-hint">{{ t('lease.noMeteredItems') }}</p>
      <div v-if="lease.readings.length" class="c-table-wrap readings">
        <table class="c-table">
          <thead><tr><th>{{ t('lease.meterItem') }}</th><th>{{ t('lease.readDate') }}</th><th>{{ t('lease.readingRange') }}</th><th>{{ t('lease.usage') }}</th><th>{{ t('lease.amount') }}</th><th>{{ t('lease.bill') }}</th><th /></tr></thead>
          <tbody>
            <tr v-for="r in lease.readings" :key="r.id">
              <td>{{ r.feeName }}</td><td>{{ r.readDate }}</td><td>{{ r.prevReading }} → {{ r.reading }}</td>
              <td>{{ r.usage }} {{ r.unit }}</td><td>{{ yuan(r.amount) }}</td><td>{{ r.billNo ?? t('lease.unbilled') }}</td>
              <td class="c-actions"><button v-if="canMeter" type="button" class="c-btn c-btn--sm c-btn--danger" @click="removeReading(r)">{{ t('console.delete') }}</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <BillDialog v-model="billOpen" :bill-id="billId" @changed="load" />
    <CheckoutDialog v-if="checkoutOpen" v-model="checkoutOpen" :lease="lease" @done="(l) => (lease = l)" />
  </template>
</template>

<style scoped>
.head { display: grid; gap: 14px; }
.head__title { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.head__title h2 { margin: 0; }
.facts { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.facts div { padding: 10px; border: 1px solid var(--rule); border-radius: 10px; background: var(--paper); }
.facts dt { color: var(--ink-muted); font-size: 12px; font-weight: 700; }
.facts dd { margin-top: 2px; font-weight: 800; }
.facts__wide { grid-column: 1 / -1; }
.link { text-decoration: underline; }
.muted td { color: var(--ink-muted); }
.readings { margin-top: 12px; }
</style>
