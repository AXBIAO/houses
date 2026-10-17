<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { Member } from '@/features/console/types'
import { showToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/authStore'

defineOptions({ name: 'LandlordMembers' })

const { t } = useI18n()
const auth = useAuthStore()
const members = ref<Member[]>([])
const form = reactive({ account: '', role: 'staff' as Member['role'] })
const saving = ref(false)
const errorText = ref('')

async function load() {
  try {
    members.value = (await landlordApi.members()).items
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function add() {
  errorText.value = ''
  if (form.account.trim().length < 3) {
    errorText.value = t('auth.contactRequired')
    return
  }
  saving.value = true
  try {
    await landlordApi.addMember(form.account.trim(), form.role)
    form.account = ''
    showToast(t('console.memberAdded'))
    await load()
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

async function remove(member: Member) {
  if (!window.confirm(t('console.confirmRemoveMember', { name: member.username }))) return
  try {
    await landlordApi.removeMember(member.userId)
    await load()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

onMounted(load)
</script>

<template>
  <form v-if="auth.isLandlordOwner" class="c-card member-form" novalidate @submit.prevent="add">
    <h2>{{ t('console.addMember') }}</h2>
    <p class="c-hint">{{ t('console.addMemberHint') }}</p>
    <div class="member-form__row">
      <input v-model="form.account" class="c-input" maxlength="120" :placeholder="t('auth.account')" :aria-label="t('auth.account')" />
      <select v-model="form.role" class="c-select member-form__role" :aria-label="t('console.col.role')">
        <option value="staff">{{ t('console.role.staff') }}</option>
        <option value="owner">{{ t('console.role.owner') }}</option>
      </select>
      <button type="submit" class="c-btn c-btn--primary" :disabled="saving">{{ t('console.add') }}</button>
    </div>
    <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
  </form>
  <p v-else class="c-hint">{{ t('console.ownerOnly') }}</p>

  <div class="c-table-wrap">
    <table class="c-table">
      <thead><tr><th>{{ t('auth.username') }}</th><th>{{ t('auth.account') }}</th><th>{{ t('console.col.role') }}</th><th /></tr></thead>
      <tbody>
        <tr v-for="m in members" :key="m.userId">
          <td>{{ m.username }}<span v-if="m.userId === auth.user?.id" class="c-hint">（{{ t('console.you') }}）</span></td>
          <td>{{ m.email || m.phone }}</td>
          <td><span class="c-badge" :data-tone="m.role === 'owner' ? 'good' : 'muted'">{{ t(`console.role.${m.role}`) }}</span></td>
          <td class="c-actions">
            <button v-if="auth.isLandlordOwner" type="button" class="c-btn c-btn--sm c-btn--danger" @click="remove(m)">{{ t('console.remove') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.member-form__row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.member-form__row .c-input { flex: 1; min-width: 220px; }
.member-form__role { width: auto; }
</style>
