<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Trash2 } from 'lucide-vue-next'
import ConsoleDialog from './ConsoleDialog.vue'
import { leasingApi } from '@/features/console/leasingApi'
import type { CheckoutResult, LeaseDetail } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { todayIso, yuan } from '@/features/console/money'

const props = defineProps<{ lease: LeaseDetail }>()
const emit = defineEmits<{ done: [lease: LeaseDetail, result: CheckoutResult] }>()
const open = defineModel<boolean>({ required: true })
const { t } = useI18n()

const form = reactive({ checkoutDate: todayIso(), note: '' })
const extras = ref<{ name: string; amount: number | '' }[]>([])
const busy = ref(false)
const errorText = ref('')
const result = ref<CheckoutResult | null>(null)
const depositHeld = computed(() => props.lease.bills.find(b => b.kind === 'deposit' && b.status !== 'void')?.paidAmount ?? 0)
const unbilledMeters = computed(() => props.lease.readings.filter(r => r.billId === null && r.amount > 0).length)

function addExtra() {
  extras.value = [...extras.value, { name: '', amount: '' }]
}
function removeExtra(index: number) {
  extras.value = extras.value.filter((_, i) => i !== index)
}

async function submit() {
  errorText.value = ''
  const cleaned = extras.value.filter(e => e.name.trim() || e.amount !== '')
  if (cleaned.some(e => !e.name.trim() || !(Number(e.amount) > 0))) {
    errorText.value = t('lease.errors.extra')
    return
  }
  if (!window.confirm(t('lease.confirmCheckout'))) return
  busy.value = true
  try {
    const res = await leasingApi.checkout(props.lease.id, {
      checkoutDate: form.checkoutDate, note: form.note.trim(),
      extras: cleaned.map(e => ({ name: e.name.trim(), amount: Number(e.amount) })),
    })
    result.value = res.result
    emit('done', res.lease, res.result)
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <ConsoleDialog v-model="open" :title="t('lease.checkout')">
    <template v-if="result">
      <p><strong>{{ t('lease.checkoutDone') }}</strong></p>
      <ul class="result">
        <li>{{ t('lease.result.voided', { n: result.voidedBills }) }}</li>
        <li>{{ t('lease.result.offset', { amount: yuan(result.depositOffset) }) }}</li>
        <li><strong>{{ t('lease.result.refund', { amount: yuan(result.depositRefund) }) }}</strong></li>
        <li :class="{ 'c-error': result.outstanding > 0 }">{{ t('lease.result.outstanding', { amount: yuan(result.outstanding) }) }}</li>
      </ul>
      <p class="c-hint">{{ t('lease.refundOffline') }}</p>
      <button type="button" class="c-btn c-btn--primary" @click="open = false">{{ t('common.close') }}</button>
    </template>
    <form v-else class="checkout" novalidate @submit.prevent="submit">
      <ol class="steps c-hint">
        <li>{{ t('lease.checkoutStep1') }}</li>
        <li>{{ t('lease.checkoutStep2', { n: unbilledMeters }) }}</li>
        <li>{{ t('lease.checkoutStep3', { amount: yuan(depositHeld) }) }}</li>
      </ol>
      <label class="c-field">{{ t('lease.checkoutDate') }}
        <input v-model="form.checkoutDate" class="c-input" type="date" :min="lease.startDate" :max="todayIso()" required />
      </label>
      <section class="extras">
        <div class="c-toolbar">
          <strong>{{ t('lease.extras') }}</strong>
          <span class="c-hint">{{ t('lease.extrasHint') }}</span>
          <span class="c-toolbar__spacer" />
          <button type="button" class="c-btn c-btn--sm" @click="addExtra"><Plus :size="14" aria-hidden="true" />{{ t('console.add') }}</button>
        </div>
        <div v-for="(extra, index) in extras" :key="index" class="extras__row">
          <input v-model="extra.name" class="c-input" maxlength="30" :placeholder="t('lease.extraName')" :aria-label="t('lease.extraName')" />
          <input v-model.number="extra.amount" class="c-input" type="number" min="0.01" step="0.01" :placeholder="t('lease.amount')" :aria-label="t('lease.amount')" />
          <button type="button" class="c-btn c-btn--sm c-btn--danger" :aria-label="t('console.delete')" @click="removeExtra(index)"><Trash2 :size="14" aria-hidden="true" /></button>
        </div>
      </section>
      <label class="c-field">{{ t('lease.note') }}<textarea v-model="form.note" class="c-textarea" rows="2" maxlength="500" /></label>
      <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
      <button type="submit" class="c-btn c-btn--primary" :disabled="busy">{{ t('lease.confirmCheckoutButton') }}</button>
    </form>
  </ConsoleDialog>
</template>

<style scoped>
.checkout { display: grid; gap: 14px; }
.steps { display: grid; gap: 4px; padding-left: 18px; list-style: decimal; }
.extras { display: grid; gap: 8px; }
.extras__row { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) auto; gap: 8px; }
.result { display: grid; gap: 6px; padding-left: 18px; list-style: disc; }
.checkout > .c-btn { justify-self: end; }
</style>
