<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import { adminApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { AdminLandlord } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'AdminLandlords' })

const PHONE_RE = /^1\d{10}$/
const { t } = useI18n()
const items = ref<AdminLandlord[]>([])
const keyword = ref('')
const loading = ref(false)
const creating = ref(false)
const saving = ref(false)
const errorText = ref('')
const form = reactive({ name: '', contactName: '', contactPhone: '', ownerAccount: '' })

async function load() {
  loading.value = true
  try {
    items.value = (await adminApi.landlords({ q: keyword.value.trim() || undefined, pageSize: 100 })).items
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  } finally {
    loading.value = false
  }
}

async function create() {
  errorText.value = ''
  if (!form.name.trim() || !form.ownerAccount.trim()) {
    errorText.value = t('console.errors.landlordFields')
    return
  }
  if (form.contactPhone && !PHONE_RE.test(form.contactPhone.trim())) {
    errorText.value = t('inquiry.phoneInvalid')
    return
  }
  saving.value = true
  try {
    await adminApi.createLandlord({
      name: form.name.trim(), contactName: form.contactName.trim() || null,
      contactPhone: form.contactPhone.trim() || null, ownerAccount: form.ownerAccount.trim(),
    })
    Object.assign(form, { name: '', contactName: '', contactPhone: '', ownerAccount: '' })
    creating.value = false
    showToast(t('console.landlordCreated'))
    await load()
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

async function toggle(landlord: AdminLandlord) {
  const next = landlord.status === 'active' ? 'disabled' : 'active'
  if (next === 'disabled' && !window.confirm(t('console.confirmDisable', { name: landlord.name }))) return
  try {
    const saved = await adminApi.updateLandlord(landlord.id, { status: next })
    items.value = items.value.map(l => (l.id === saved.id ? { ...l, status: saved.status } : l))
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

onMounted(load)
</script>

<template>
  <div class="c-toolbar">
    <form class="search" @submit.prevent="load">
      <input v-model="keyword" class="c-input" type="search" maxlength="40" :placeholder="t('console.searchLandlords')" :aria-label="t('console.searchLandlords')" />
    </form>
    <span class="c-toolbar__spacer" />
    <button type="button" class="c-btn c-btn--primary" @click="creating = !creating"><Plus :size="16" aria-hidden="true" />{{ t('console.newLandlord') }}</button>
  </div>

  <form v-if="creating" class="c-card" novalidate @submit.prevent="create">
    <h2>{{ t('console.newLandlord') }}</h2>
    <p class="c-hint">{{ t('console.newLandlordHint') }}</p>
    <div class="c-form-grid">
      <label class="c-field">{{ t('console.field.landlordName') }}<input v-model="form.name" class="c-input" maxlength="40" required /></label>
      <label class="c-field">{{ t('console.field.ownerAccount') }}<input v-model="form.ownerAccount" class="c-input" maxlength="120" required /></label>
      <label class="c-field">{{ t('console.field.contactName') }}<input v-model="form.contactName" class="c-input" maxlength="20" /></label>
      <label class="c-field">{{ t('console.field.contactPhone') }}<input v-model="form.contactPhone" class="c-input" inputmode="numeric" maxlength="11" /></label>
    </div>
    <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
    <div class="c-toolbar actions">
      <button type="button" class="c-btn" @click="creating = false">{{ t('common.cancel') }}</button>
      <button type="submit" class="c-btn c-btn--primary" :disabled="saving">{{ t('console.create') }}</button>
    </div>
  </form>

  <p v-if="loading && !items.length" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!items.length" class="c-empty"><p>{{ t('common.empty') }}</p></div>
  <div v-else class="c-table-wrap">
    <table class="c-table">
      <thead>
        <tr>
          <th>{{ t('console.field.landlordName') }}</th><th>{{ t('console.col.owners') }}</th><th>{{ t('console.field.contactPhone') }}</th>
          <th>{{ t('console.col.listingsPublished') }}</th><th>{{ t('console.col.members') }}</th><th>{{ t('console.col.status') }}</th><th />
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in items" :key="l.id">
          <td><strong>{{ l.name }}</strong><p class="c-hint">#{{ l.id }}{{ l.contactName ? ` · ${l.contactName}` : '' }}</p></td>
          <td>{{ l.owners || '—' }}</td>
          <td>{{ l.contactPhone || '—' }}</td>
          <td>{{ l.publishedCount }} / {{ l.listingCount }}</td>
          <td>{{ l.memberCount }}</td>
          <td><span class="c-badge" :data-tone="l.status === 'active' ? 'good' : 'bad'">{{ t(`console.landlordStatus.${l.status}`) }}</span></td>
          <td class="c-actions">
            <RouterLink :to="{ path: '/admin/listings', query: { landlordId: l.id } }" class="c-btn c-btn--sm">{{ t('console.tabs.listings') }}</RouterLink>
            <button type="button" class="c-btn c-btn--sm" :class="{ 'c-btn--danger': l.status === 'active' }" @click="toggle(l)">
              {{ l.status === 'active' ? t('console.disable') : t('console.enable') }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.search { flex: 1; min-width: 200px; max-width: 360px; }
.actions { justify-content: flex-end; margin-top: 12px; }
</style>
