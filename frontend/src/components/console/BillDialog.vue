<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ConsoleDialog from './ConsoleDialog.vue'
import LeasingBadge from './LeasingBadge.vue'
import { leasingApi } from '@/features/console/leasingApi'
import { MANUAL_METHODS, type BillDetail, type ManualMethod, type Payment } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { todayIso, yuan } from '@/features/console/money'
import { showToast } from '@/composables/useToast'

/** 账单详情：登记线下收款、设置减免、作废登记错的收款。平台不经手任何钱款。 */
const props = defineProps<{ billId: number | null }>()
const emit = defineEmits<{ changed: [] }>()
const open = defineModel<boolean>({ required: true })
const { t } = useI18n()

const bill = ref<BillDetail | null>(null)
const busy = ref(false)
const errorText = ref('')
const payForm = reactive({ amount: 0, method: 'wechat' as ManualMethod, paidOn: todayIso(), note: '' })
const discountForm = reactive({ amount: 0, note: '' })
const editable = computed(() => bill.value !== null && bill.value.status !== 'void')
const canPay = computed(() => editable.value && (bill.value?.outstanding ?? 0) > 0)

async function load() {
  if (props.billId === null) return
  errorText.value = ''
  try {
    bill.value = await leasingApi.bill(props.billId)
    payForm.amount = bill.value.outstanding
    discountForm.amount = bill.value.discountAmount
    discountForm.note = bill.value.note
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  }
}

async function run(action: () => Promise<BillDetail | unknown>, done: string) {
  busy.value = true
  errorText.value = ''
  try {
    const result = await action()
    if (result && typeof result === 'object' && 'items' in (result as BillDetail)) {
      bill.value = result as BillDetail
      payForm.amount = bill.value.outstanding
    } else {
      await load()
    }
    showToast(t(done))
    emit('changed')
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    busy.value = false
  }
}

function pay() {
  if (!bill.value) return
  if (!(payForm.amount > 0)) {
    errorText.value = t('lease.errors.amount')
    return
  }
  const id = bill.value.id
  void run(() => leasingApi.pay(id, { amount: payForm.amount, method: payForm.method, paidOn: payForm.paidOn || null, note: payForm.note.trim() }), 'lease.paid')
}

function discount() {
  if (!bill.value) return
  const id = bill.value.id
  void run(() => leasingApi.discount(id, { amount: Number(discountForm.amount) || 0, note: discountForm.note.trim() }), 'console.saved')
}

function voidPayment(payment: Payment) {
  if (!window.confirm(t('lease.confirmVoidPayment', { amount: yuan(payment.amount) }))) return
  void run(() => leasingApi.voidPayment(payment.id), 'lease.paymentVoided')
}

watch(open, (value) => { if (value) void load() })
</script>

<template>
  <ConsoleDialog v-model="open" :title="bill ? `${t(`lease.billKind.${bill.kind}`)} · ${bill.billNo}` : t('lease.bill')" wide>
    <p v-if="!bill && !errorText" class="c-hint">{{ t('common.loading') }}</p>
    <template v-if="bill">
      <div class="bill-head">
        <LeasingBadge :bill="bill.status" :overdue="bill.isOverdue" />
        <span>{{ bill.renterName }} · {{ bill.listingTitle }}</span>
        <span v-if="bill.periodStart" class="c-hint">{{ bill.periodStart }} ~ {{ bill.periodEnd }}</span>
        <span class="c-hint">{{ t('lease.dueDate') }} {{ bill.dueDate }}</span>
      </div>
      <dl class="amounts">
        <div><dt>{{ t('lease.total') }}</dt><dd>{{ yuan(bill.totalAmount) }}</dd></div>
        <div><dt>{{ t('lease.discount') }}</dt><dd>{{ yuan(bill.discountAmount) }}</dd></div>
        <div><dt>{{ t('lease.paidAmount') }}</dt><dd>{{ yuan(bill.paidAmount) }}</dd></div>
        <div class="amounts__due"><dt>{{ t('lease.outstanding') }}</dt><dd>{{ yuan(bill.outstanding) }}</dd></div>
      </dl>

      <div class="c-table-wrap">
        <table class="c-table">
          <thead><tr><th>{{ t('lease.item') }}</th><th>{{ t('lease.quantity') }}</th><th>{{ t('lease.unitPrice') }}</th><th>{{ t('lease.amount') }}</th></tr></thead>
          <tbody>
            <tr v-for="item in bill.items" :key="item.id">
              <td>{{ item.name }}</td><td>{{ item.quantity }}</td><td>{{ item.unitPrice }}</td><td>{{ yuan(item.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <form v-if="canPay" class="c-card sub-card" novalidate @submit.prevent="pay">
        <h3>{{ t('lease.recordPayment') }}</h3>
        <p class="c-hint">{{ t('lease.recordOnly') }}</p>
        <div class="c-form-grid">
          <label class="c-field">{{ t('lease.amount') }}<input v-model.number="payForm.amount" class="c-input" type="number" min="0.01" step="0.01" :max="bill.outstanding" /></label>
          <label class="c-field">{{ t('lease.method') }}
            <select v-model="payForm.method" class="c-select">
              <option v-for="m in MANUAL_METHODS" :key="m" :value="m">{{ t(`lease.methods.${m}`) }}</option>
            </select>
          </label>
          <label class="c-field">{{ t('lease.paidOn') }}<input v-model="payForm.paidOn" class="c-input" type="date" :max="todayIso()" /></label>
          <label class="c-field">{{ t('lease.note') }}<input v-model="payForm.note" class="c-input" maxlength="200" /></label>
        </div>
        <button type="submit" class="c-btn c-btn--primary" :disabled="busy">{{ t('lease.recordPayment') }}</button>
      </form>

      <form v-if="editable && bill.kind !== 'deposit'" class="c-card sub-card" novalidate @submit.prevent="discount">
        <h3>{{ t('lease.discount') }}</h3>
        <p class="c-hint">{{ t('lease.discountHint') }}</p>
        <div class="c-form-grid">
          <label class="c-field">{{ t('lease.discountTotal') }}<input v-model.number="discountForm.amount" class="c-input" type="number" min="0" step="0.01" /></label>
          <label class="c-field">{{ t('lease.note') }}<input v-model="discountForm.note" class="c-input" maxlength="200" /></label>
        </div>
        <button type="submit" class="c-btn" :disabled="busy">{{ t('console.save') }}</button>
      </form>

      <section v-if="bill.payments.length">
        <h3 class="c-section-title">{{ t('lease.payments') }}</h3>
        <ul class="payments">
          <li v-for="p in bill.payments" :key="p.id" :class="{ 'is-void': p.status === 'void' }">
            <strong>{{ yuan(p.amount) }}</strong>
            <span class="c-badge">{{ t(`lease.methods.${p.method}`) }}</span>
            <span class="c-hint">{{ p.paidOn }}{{ p.note ? ` · ${p.note}` : '' }}</span>
            <span v-if="p.status === 'void'" class="c-badge" data-tone="muted">{{ t('lease.voided') }}</span>
            <button
              v-else-if="MANUAL_METHODS.includes(p.method as ManualMethod)" type="button"
              class="c-btn c-btn--sm c-btn--danger" :disabled="busy" @click="voidPayment(p)"
            >{{ t('lease.voidPayment') }}</button>
          </li>
        </ul>
      </section>
    </template>
    <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
  </ConsoleDialog>
</template>

<style scoped>
.bill-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.amounts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.amounts div { padding: 10px; border: 1px solid var(--rule); border-radius: 10px; background: var(--paper); }
.amounts dt { color: var(--ink-muted); font-size: 12px; font-weight: 700; }
.amounts dd { margin-top: 2px; font-size: 17px; font-weight: 900; }
.amounts__due { border-color: var(--rule-strong) !important; background: var(--acid-soft) !important; color: var(--ink); }
:root[data-theme='dark'] .amounts__due { background: var(--paper-muted) !important; }
.sub-card { display: grid; gap: 10px; box-shadow: none; }
.sub-card h3 { font-size: 16px; font-weight: 900; }
.sub-card .c-btn { justify-self: end; }
.payments { display: grid; gap: 8px; }
.payments li { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 8px; }
.payments li .c-btn { margin-left: auto; }
.payments li.is-void strong { text-decoration: line-through; color: var(--ink-muted); }
@media (max-width: 640px) { .amounts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
