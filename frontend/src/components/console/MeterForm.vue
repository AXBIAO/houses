<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { leasingApi } from '@/features/console/leasingApi'
import type { FeeItem, LeaseFee } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { todayIso, yuan } from '@/features/console/money'
import { showToast } from '@/composables/useToast'

/** 抄表：上次读数自动带出；首次或换表时手填起始读数。费用按租约约定单价，没有约定用项目默认价。 */
const props = defineProps<{ leaseId: number; meteredItems: FeeItem[]; leaseFees: LeaseFee[] }>()
const emit = defineEmits<{ saved: [] }>()
const { t } = useI18n()

const form = reactive({ feeItemId: props.meteredItems[0]?.id ?? 0, reading: '' as number | '', readDate: todayIso(), prevReading: '' as number | '' })
const last = ref<{ reading: number; readDate: string } | null>(null)
const busy = ref(false)
const errorText = ref('')

const item = computed(() => props.meteredItems.find(i => i.id === form.feeItemId) ?? null)
const unitPrice = computed(() => props.leaseFees.find(f => f.feeItemId === form.feeItemId)?.price ?? item.value?.defaultPrice ?? 0)
const start = computed(() => (form.prevReading !== '' ? Number(form.prevReading) : last.value?.reading ?? null))
const estimate = computed(() => (form.reading !== '' && start.value !== null && Number(form.reading) >= start.value
  ? (Number(form.reading) - start.value) * unitPrice.value : null))

async function loadLast() {
  last.value = null
  if (!form.feeItemId) return
  try {
    last.value = (await leasingApi.lastReading(props.leaseId, form.feeItemId)).last
  } catch {
    last.value = null
  }
}

async function submit() {
  errorText.value = ''
  if (form.reading === '' || (start.value === null)) {
    errorText.value = t(start.value === null ? 'lease.errors.prevReading' : 'lease.errors.reading')
    return
  }
  busy.value = true
  try {
    const res = await leasingApi.addReading(props.leaseId, {
      feeItemId: form.feeItemId, reading: Number(form.reading), readDate: form.readDate,
      prevReading: form.prevReading === '' ? null : Number(form.prevReading),
    })
    showToast(t('lease.meterSaved', { amount: yuan(res.amount) }))
    form.reading = ''
    form.prevReading = ''
    await loadLast()
    emit('saved')
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    busy.value = false
  }
}

watch(() => form.feeItemId, loadLast, { immediate: true })
</script>

<template>
  <form class="meter" novalidate @submit.prevent="submit">
    <div class="c-form-grid">
      <label class="c-field">{{ t('lease.meterItem') }}
        <select v-model.number="form.feeItemId" class="c-select">
          <option v-for="i in meteredItems" :key="i.id" :value="i.id">{{ i.name }}</option>
        </select>
      </label>
      <label class="c-field">{{ t('lease.prevReading') }}
        <input v-model.number="form.prevReading" class="c-input" type="number" min="0" step="0.01" :placeholder="last ? String(last.reading) : t('lease.firstReading')" />
      </label>
      <label class="c-field">{{ t('lease.reading') }}<input v-model.number="form.reading" class="c-input" type="number" min="0" step="0.01" required /></label>
      <label class="c-field">{{ t('lease.readDate') }}<input v-model="form.readDate" class="c-input" type="date" :min="last?.readDate" :max="todayIso()" /></label>
    </div>
    <p class="c-hint">
      {{ last ? t('lease.lastReading', { reading: last.reading, date: last.readDate }) : t('lease.noLastReading') }}
      · {{ t('lease.unitPriceIs', { price: unitPrice, unit: item?.unit || '' }) }}
      <template v-if="estimate !== null"> · {{ t('lease.estimate', { amount: yuan(estimate) }) }}</template>
    </p>
    <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
    <button type="submit" class="c-btn c-btn--primary" :disabled="busy">{{ t('lease.saveReading') }}</button>
  </form>
</template>

<style scoped>
.meter { display: grid; gap: 10px; }
.meter > .c-btn { justify-self: end; }
</style>
