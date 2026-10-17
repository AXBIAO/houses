<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { LogOut } from 'lucide-vue-next'
import ConsoleDialog from '@/components/console/ConsoleDialog.vue'
import { errorMessage } from '@/features/console/errors'
import { showToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/authStore'
import '@/console.css'

const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ logout: [] }>()
const { t } = useI18n()
const auth = useAuthStore()
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const saving = ref(false)
const errorText = ref('')

watch(open, (value) => {
  if (value) Object.assign(form, { oldPassword: '', newPassword: '', confirm: '' })
  errorText.value = ''
})

async function changePassword() {
  errorText.value = ''
  if (form.newPassword.length < 8) {
    errorText.value = t('auth.passwordHint')
    return
  }
  if (form.newPassword !== form.confirm) {
    errorText.value = t('account.mismatch')
    return
  }
  saving.value = true
  try {
    await auth.changePassword(form.oldPassword, form.newPassword)
    showToast(t('account.changed'))
    open.value = false
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

function logout() {
  open.value = false
  emit('logout')
}
</script>

<template>
  <ConsoleDialog v-model="open" :title="t('navigation.accountSettings')">
    <dl v-if="auth.user" class="info">
      <div><dt>{{ t('auth.username') }}</dt><dd>{{ auth.user.username }}</dd></div>
      <div><dt>{{ t('auth.account') }}</dt><dd>{{ auth.user.email || auth.user.phone }}</dd></div>
      <div><dt>{{ t('account.role') }}</dt><dd>{{ t(`account.roles.${auth.user.role}`) }}<template v-if="auth.user.landlord"> · {{ auth.user.landlord.name }}（{{ t(`console.role.${auth.user.landlord.role}`) }}）</template></dd></div>
    </dl>
    <form class="pw" novalidate @submit.prevent="changePassword">
      <h3>{{ t('account.changePassword') }}</h3>
      <label class="c-field">{{ t('account.oldPassword') }}<input v-model="form.oldPassword" class="c-input" type="password" autocomplete="current-password" /></label>
      <label class="c-field">{{ t('account.newPassword') }}<input v-model="form.newPassword" class="c-input" type="password" autocomplete="new-password" :placeholder="t('auth.passwordHint')" /></label>
      <label class="c-field">{{ t('account.confirmPassword') }}<input v-model="form.confirm" class="c-input" type="password" autocomplete="new-password" /></label>
      <p class="c-hint">{{ t('account.otherDevices') }}</p>
      <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
      <button type="submit" class="c-btn c-btn--primary" :disabled="saving">{{ t('account.changePassword') }}</button>
    </form>
    <button type="button" class="c-btn c-btn--danger logout" @click="logout"><LogOut :size="16" aria-hidden="true" />{{ t('navigation.logout') }}</button>
  </ConsoleDialog>
</template>

<style scoped>
.info { display: grid; gap: 8px; }
.info div { display: flex; gap: 12px; }
.info dt { width: 72px; color: var(--ink-muted); font-size: 13px; font-weight: 700; }
.info dd { font-weight: 800; overflow-wrap: anywhere; }
.pw { display: grid; gap: 10px; padding-top: 14px; border-top: 1px solid var(--rule); }
.pw h3 { font-size: 16px; font-weight: 900; }
.pw > .c-btn { justify-self: end; }
.logout { justify-self: start; }
</style>
