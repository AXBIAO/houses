<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { landlordApi } from '@/features/console/api'
import { leasingApi } from '@/features/console/leasingApi'
import { PAY_CYCLES, type FeeItem, type PlannedBill, type Renter, type SignInput } from '@/features/console/leasingTypes'
import type { ConsoleListing } from '@/features/console/types'
import { errorMessage } from '@/features/console/errors'
import { yuan } from '@/features/console/money'
import { defaultsFromListing, emptySignForm, leaseEnd, toSignInput, type SignForm } from '@/features/console/signForm'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LeaseSign' })

const MONTH_PRESETS = [3, 6, 12, 24] as const
const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const listings = ref<ConsoleListing[]>([])
const renters = ref<Renter[]>([])
const feeItems = ref<FeeItem[]>([])
const form = ref<SignForm | null>(null)
const preview = ref<{ bills: PlannedBill[]; total: number } | null>(null)
const previewFor = ref('')
const busy = ref(false)
const errorText = ref('')

const activeFees = computed(() => feeItems.value.filter(f => f.active))
const currentInput = computed(() => (form.value ? toSignInput(form.value) : null))
const previewStale = computed(() => !preview.value || previewFor.value !== JSON.stringify(currentInput.value))

async function load() {
  try {
    const [l, r, f] = await Promise.all([landlordApi.listings({ pageSize: 100 }), leasingApi.renters(), leasingApi.feeItems()])
    listings.value = l.items.filter(x => x.rentType !== 'short')
    renters.value = r.items
    feeItems.value = f.items
    const listingId = Number(route.query.listingId) || listings.value[0]?.id || 0
    const inquiryId = Number(route.query.inquiryId) || null
    form.value = { ...emptySignForm(f.items, listingId, inquiryId), ...defaultsFromListing(listings.value.find(x => x.id === listingId)) }
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  }
}

function pickListing(id: number) {
  if (!form.value) return
  form.value = { ...form.value, listingId: id, ...defaultsFromListing(listings.value.find(x => x.id === id)) }
}
function setMonths(months: number) {
  if (!form.value) return
  form.value.months = months
  form.value.endDate = leaseEnd(form.value.startDate, months)
}

function validInput(): SignInput | null {
  const result = currentInput.value
  if (!result || 'errorKey' in result) {
    errorText.value = result ? t(result.errorKey) : ''
    return null
  }
  errorText.value = ''
  return result.input
}

async function runPreview() {
  const input = validInput()
  if (!input) return
  busy.value = true
  try {
    preview.value = await leasingApi.preview(input)
    previewFor.value = JSON.stringify(currentInput.value)
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    busy.value = false
  }
}

async function sign() {
  const input = validInput()
  if (!input) return
  busy.value = true
  try {
    const lease = await leasingApi.sign(input)
    showToast(t('lease.signed', { no: lease.leaseNo }))
    await router.replace(`/landlord/leases/${lease.id}`)
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    busy.value = false
  }
}

watch(() => form.value?.startDate, (start) => {
  if (form.value && start) form.value.endDate = leaseEnd(start, form.value.months)
})

onMounted(load)
</script>

<template>
  <div class="c-toolbar">
    <RouterLink to="/landlord/leases" class="c-btn c-btn--sm">← {{ t('console.tabs.leases') }}</RouterLink>
    <h2 class="c-section-title title">{{ t('lease.sign') }}</h2>
  </div>
  <p v-if="!form && !errorText" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="form && !listings.length" class="c-empty"><p>{{ t('lease.needListing') }}</p></div>
  <template v-else-if="form">
    <form class="c-card" novalidate @submit.prevent="runPreview">
      <h2>{{ t('lease.stepListing') }}</h2>
      <div class="c-form-grid">
        <label class="c-field c-field--wide">{{ t('console.col.listing') }}
          <select class="c-select" :value="form.listingId" @change="pickListing(Number(($event.target as HTMLSelectElement).value))">
            <option v-for="l in listings" :key="l.id" :value="l.id">{{ l.title }}（{{ t(`rentType.${l.rentType}`) }} · {{ t(`console.status.${l.status}`) }}）</option>
          </select>
        </label>
      </div>

      <h2 class="section">{{ t('lease.stepRenter') }}</h2>
      <div class="c-toolbar">
        <label><input v-model="form.renterMode" type="radio" value="new" /> {{ t('lease.newRenter') }}</label>
        <label><input v-model="form.renterMode" type="radio" value="existing" :disabled="!renters.length" /> {{ t('lease.existingRenter') }}</label>
      </div>
      <div v-if="form.renterMode === 'existing'" class="c-form-grid">
        <label class="c-field c-field--wide">{{ t('lease.renter') }}
          <select v-model.number="form.renterId" class="c-select">
            <option :value="0" disabled>{{ t('lease.chooseRenter') }}</option>
            <option v-for="r in renters" :key="r.id" :value="r.id">{{ r.name }} · {{ r.phone }}</option>
          </select>
        </label>
      </div>
      <div v-else class="c-form-grid">
        <label class="c-field">{{ t('lease.renterName') }}<input v-model="form.newRenter.name" class="c-input" maxlength="30" /></label>
        <label class="c-field">{{ t('auth.phone') }}<input v-model="form.newRenter.phone" class="c-input" inputmode="numeric" maxlength="11" /></label>
        <label class="c-field">{{ t('lease.idCardTail') }}<input v-model="form.newRenter.idCardTail" class="c-input" maxlength="4" :placeholder="t('lease.idCardTailHint')" /></label>
      </div>

      <h2 class="section">{{ t('lease.stepTerms') }}</h2>
      <div class="c-form-grid">
        <label class="c-field">{{ t('lease.startDate') }}<input v-model="form.startDate" class="c-input" type="date" /></label>
        <div class="c-field">{{ t('lease.duration') }}
          <div class="presets">
            <button v-for="m in MONTH_PRESETS" :key="m" type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--primary': form.months === m && form.endDate === leaseEnd(form.startDate, m) }" @click="setMonths(m)">{{ t('home.months', { n: m }) }}</button>
          </div>
        </div>
        <label class="c-field">{{ t('lease.endDate') }}<input v-model="form.endDate" class="c-input" type="date" :min="form.startDate" /></label>
        <label class="c-field">{{ t('lease.monthlyRent') }}<input v-model.number="form.monthlyRent" class="c-input" type="number" min="0" step="0.01" /></label>
        <label class="c-field">{{ t('lease.deposit') }}<input v-model.number="form.deposit" class="c-input" type="number" min="0" step="0.01" /></label>
        <label class="c-field">{{ t('lease.payCycle') }}
          <select v-model.number="form.payCycleMonths" class="c-select">
            <option v-for="c in PAY_CYCLES" :key="c" :value="c">{{ t(`lease.cycles.${c}`) }}</option>
          </select>
        </label>
        <label class="c-field">{{ t('lease.advanceDays') }}<input v-model.number="form.advanceDays" class="c-input" type="number" min="0" max="60" /></label>
        <label class="c-field">{{ t('lease.occupants') }}<input v-model.number="form.occupants" class="c-input" type="number" min="1" max="20" /></label>
      </div>

      <h2 class="section">{{ t('lease.stepFees') }}</h2>
      <p v-if="!activeFees.length" class="c-hint">{{ t('lease.noFeeItems') }} <RouterLink to="/landlord/settings" class="link">{{ t('console.tabs.settings') }}</RouterLink></p>
      <ul v-else class="fees">
        <li v-for="f in activeFees" :key="f.id">
          <label class="fees__pick"><input v-model="form.fees[f.id]!.on" type="checkbox" /> {{ f.name }}</label>
          <span class="c-badge">{{ t(`lease.feeKind.${f.kind}`) }}</span>
          <input v-model.number="form.fees[f.id]!.price" class="c-input fees__price" type="number" min="0" step="0.0001" :disabled="!form.fees[f.id]!.on" :aria-label="t('lease.price')" />
          <span class="c-hint">{{ f.kind === 'metered' ? t('lease.perUnit', { unit: f.unit || '' }) : f.kind === 'fixed' ? t('common.perMonth') : t('lease.once') }}</span>
        </li>
      </ul>

      <label class="c-field section">{{ t('lease.note') }}<textarea v-model="form.note" class="c-textarea" rows="2" maxlength="500" /></label>
      <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
      <div class="c-toolbar actions">
        <button type="submit" class="c-btn" :disabled="busy">{{ t('lease.preview') }}</button>
        <button type="button" class="c-btn c-btn--primary" :disabled="busy || previewStale" :title="previewStale ? t('lease.previewFirst') : ''" @click="sign">{{ t('lease.confirmSign') }}</button>
      </div>
    </form>

    <section v-if="preview" class="c-card" :class="{ stale: previewStale }">
      <h2>{{ t('lease.previewTitle', { n: preview.bills.length, total: yuan(preview.total) }) }}</h2>
      <p v-if="previewStale" class="c-hint">{{ t('lease.previewStale') }}</p>
      <div class="c-table-wrap">
        <table class="c-table">
          <thead><tr><th>{{ t('lease.billKindCol') }}</th><th>{{ t('lease.period') }}</th><th>{{ t('lease.dueDate') }}</th><th>{{ t('lease.items') }}</th><th>{{ t('lease.total') }}</th></tr></thead>
          <tbody>
            <tr v-for="(b, i) in preview.bills" :key="i">
              <td>{{ b.kind === 'rent' ? t('lease.periodN', { n: b.periodNo }) : t(`lease.billKind.${b.kind}`) }}</td>
              <td>{{ b.periodStart }} ~ {{ b.periodEnd }}</td>
              <td>{{ b.dueDate }}</td>
              <td class="c-hint">{{ b.items.map(x => `${x.name} ${yuan(x.amount)}`).join('，') }}</td>
              <td><strong>{{ yuan(b.totalAmount) }}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
  <p v-else-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
</template>

<style scoped>
.title { margin: 0; }
.section { margin-top: 18px; }
.presets { display: flex; flex-wrap: wrap; gap: 6px; }
.fees { display: grid; gap: 8px; }
.fees li { display: grid; grid-template-columns: minmax(120px, 1fr) auto 140px minmax(60px, auto); align-items: center; gap: 10px; }
.fees__pick { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; }
.actions { justify-content: flex-end; margin-top: 16px; }
.stale { opacity: .6; }
.link { text-decoration: underline; }
@media (max-width: 640px) { .fees li { grid-template-columns: 1fr auto; } }
</style>
