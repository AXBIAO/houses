<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { leasingApi } from '@/features/console/leasingApi'
import type { FeeItem, FeeItemInput, FeeKind, Renter } from '@/features/console/leasingTypes'
import { errorMessage } from '@/features/console/errors'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LandlordSettings' })

const KINDS: readonly FeeKind[] = ['fixed', 'one_time', 'metered']
const { t } = useI18n()
const feeItems = ref<FeeItem[]>([])
const renters = ref<Renter[]>([])
const feeForm = reactive<FeeItemInput>({ name: '', kind: 'fixed', defaultPrice: 0, unit: '', active: true })
const editingFee = ref<number | null>(null)
const feeError = ref('')

async function load() {
  try {
    const [f, r] = await Promise.all([leasingApi.feeItems(), leasingApi.renters()])
    feeItems.value = f.items
    renters.value = r.items
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

function editFee(item: FeeItem | null) {
  feeError.value = ''
  editingFee.value = item?.id ?? null
  Object.assign(feeForm, item
    ? { name: item.name, kind: item.kind, defaultPrice: item.defaultPrice, unit: item.unit, active: item.active }
    : { name: '', kind: 'fixed', defaultPrice: 0, unit: '', active: true })
}

async function saveFee() {
  feeError.value = ''
  if (!feeForm.name.trim()) {
    feeError.value = t('lease.errors.feeName')
    return
  }
  const body = { ...feeForm, name: feeForm.name.trim(), unit: feeForm.unit.trim(), defaultPrice: Number(feeForm.defaultPrice) || 0 }
  try {
    if (editingFee.value) await leasingApi.updateFeeItem(editingFee.value, body)
    else await leasingApi.createFeeItem(body)
    showToast(t('console.saved'))
    editFee(null)
    await load()
  } catch (error) {
    feeError.value = errorMessage(error, t('common.error'))
  }
}

async function removeFee(item: FeeItem) {
  if (!window.confirm(t('lease.confirmDeleteFee', { name: item.name }))) return
  try {
    await leasingApi.deleteFeeItem(item.id)
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function removeRenter(renter: Renter) {
  if (!window.confirm(t('lease.confirmDeleteRenter', { name: renter.name }))) return
  try {
    await leasingApi.deleteRenter(renter.id)
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

onMounted(load)
</script>

<template>
  <section class="c-card">
    <h2>{{ t('lease.feeItems') }}</h2>
    <p class="c-hint">{{ t('lease.feeItemsHint') }}</p>
    <form class="fee-form" novalidate @submit.prevent="saveFee">
      <input v-model="feeForm.name" class="c-input" maxlength="20" :placeholder="t('lease.feeName')" :aria-label="t('lease.feeName')" />
      <select v-model="feeForm.kind" class="c-select" :aria-label="t('lease.feeKindLabel')">
        <option v-for="k in KINDS" :key="k" :value="k">{{ t(`lease.feeKind.${k}`) }}</option>
      </select>
      <input v-model.number="feeForm.defaultPrice" class="c-input" type="number" min="0" step="0.0001" :placeholder="t('lease.price')" :aria-label="t('lease.price')" />
      <input v-model="feeForm.unit" class="c-input" maxlength="8" :placeholder="t('lease.unitPlaceholder')" :aria-label="t('lease.unit')" />
      <label class="active"><input v-model="feeForm.active" type="checkbox" /> {{ t('lease.active') }}</label>
      <button type="submit" class="c-btn c-btn--primary">{{ editingFee ? t('console.save') : t('console.add') }}</button>
      <button v-if="editingFee" type="button" class="c-btn" @click="editFee(null)">{{ t('common.cancel') }}</button>
    </form>
    <p v-if="feeError" class="c-error" role="alert">{{ feeError }}</p>
    <div v-if="feeItems.length" class="c-table-wrap list">
      <table class="c-table">
        <thead><tr><th>{{ t('lease.feeName') }}</th><th>{{ t('lease.feeKindLabel') }}</th><th>{{ t('lease.price') }}</th><th>{{ t('console.col.status') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="f in feeItems" :key="f.id">
            <td><strong>{{ f.name }}</strong></td>
            <td>{{ t(`lease.feeKind.${f.kind}`) }}</td>
            <td>{{ f.defaultPrice }}{{ f.unit ? ` / ${f.unit}` : '' }}</td>
            <td><span class="c-badge" :data-tone="f.active ? 'good' : 'muted'">{{ f.active ? t('lease.active') : t('lease.inactive') }}</span></td>
            <td class="c-actions">
              <button type="button" class="c-btn c-btn--sm" @click="editFee(f)">{{ t('console.edit') }}</button>
              <button type="button" class="c-btn c-btn--sm c-btn--danger" @click="removeFee(f)">{{ t('console.delete') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="c-card">
    <h2>{{ t('lease.renters') }}</h2>
    <p class="c-hint">{{ t('lease.rentersHint') }}</p>
    <p v-if="!renters.length" class="c-hint">{{ t('common.empty') }}</p>
    <div v-else class="c-table-wrap list">
      <table class="c-table">
        <thead><tr><th>{{ t('lease.renterName') }}</th><th>{{ t('auth.phone') }}</th><th>{{ t('lease.idCardTail') }}</th><th>{{ t('lease.openLeases') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="r in renters" :key="r.id">
            <td>{{ r.name }}</td><td>{{ r.phone }}</td><td>{{ r.idCardTail ? `****${r.idCardTail}` : '—' }}</td><td>{{ r.openLeases ?? 0 }}</td>
            <td class="c-actions"><button type="button" class="c-btn c-btn--sm c-btn--danger" @click="removeRenter(r)">{{ t('console.delete') }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.fee-form { display: grid; grid-template-columns: minmax(120px, 2fr) minmax(110px, 1fr) minmax(90px, 1fr) minmax(80px, 1fr) auto auto auto; align-items: center; gap: 8px; margin-top: 10px; }
.active { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700; white-space: nowrap; }
.list { margin-top: 12px; }
@media (max-width: 860px) { .fee-form { grid-template-columns: 1fr 1fr; } }
</style>
