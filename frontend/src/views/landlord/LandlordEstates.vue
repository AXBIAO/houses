<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import EstateForm from '@/components/console/EstateForm.vue'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { Estate, EstateInput } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'LandlordEstates' })

const { t } = useI18n()
const estates = ref<Estate[]>([])
const loading = ref(true)
/** null = 表单关闭；'new' = 新建；Estate = 编辑 */
const editing = ref<Estate | 'new' | null>(null)
const saving = ref(false)
const formError = ref('')

async function load() {
  loading.value = true
  try {
    estates.value = (await landlordApi.estates()).items
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

function open(target: Estate | 'new') {
  formError.value = ''
  editing.value = target
}

async function submit(input: EstateInput) {
  saving.value = true
  formError.value = ''
  try {
    const target = editing.value
    if (target && target !== 'new') await landlordApi.updateEstate(target.id, input)
    else await landlordApi.createEstate(input)
    showToast(t('console.saved'))
    editing.value = null
    await load()
  } catch (error) {
    formError.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

async function remove(estate: Estate) {
  if (!window.confirm(t('console.confirmDeleteEstate', { name: estate.name }))) return
  try {
    await landlordApi.deleteEstate(estate.id)
    showToast(t('console.deleted'))
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

onMounted(load)
</script>

<template>
  <div class="c-toolbar">
    <span class="c-hint">{{ t('console.estateHint') }}</span>
    <span class="c-toolbar__spacer" />
    <button type="button" class="c-btn c-btn--primary" @click="open('new')"><Plus :size="16" aria-hidden="true" />{{ t('console.newEstate') }}</button>
  </div>

  <EstateForm
    v-if="editing" :key="editing === 'new' ? 'new' : editing.id"
    :estate="editing === 'new' ? null : editing" :saving="saving" :error-text="formError"
    @submit="submit" @cancel="editing = null"
  />

  <p v-if="loading" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!estates.length" class="c-empty"><p>{{ t('console.noEstates') }}</p></div>
  <div v-else class="c-table-wrap">
    <table class="c-table">
      <thead>
        <tr><th>{{ t('console.field.estateName') }}</th><th>{{ t('filters.district') }}</th><th>{{ t('console.field.address') }}</th><th>{{ t('console.col.listingCount') }}</th><th /></tr>
      </thead>
      <tbody>
        <tr v-for="e in estates" :key="e.id">
          <td><strong>{{ e.name }}</strong></td>
          <td>{{ e.city }} · {{ e.district }}</td>
          <td>{{ e.address || '—' }}</td>
          <td>{{ e.listingCount ?? 0 }}</td>
          <td class="c-actions">
            <button type="button" class="c-btn c-btn--sm" @click="open(e)">{{ t('console.edit') }}</button>
            <button type="button" class="c-btn c-btn--sm c-btn--danger" :disabled="(e.listingCount ?? 0) > 0" :title="(e.listingCount ?? 0) > 0 ? t('console.estateInUse') : ''" @click="remove(e)">{{ t('console.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
