<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/authStore'
import { useDockSuppression } from '@/composables/useDockSuppression'
import { showToast } from '@/composables/useToast'
import { ApiError } from '@/services/http/apiClient'

const open = defineModel<boolean>({ required: true })
const { t } = useI18n()
const auth = useAuthStore()
const dialog = ref<HTMLDialogElement | null>(null)
const mode = ref<'login' | 'register'>('login')
const submitting = ref(false)
const errorText = ref('')
const form = reactive({ account: '', email: '', phone: '', username: '', password: '' })
const title = computed(() => t(mode.value === 'login' ? 'auth.loginTitle' : 'auth.registerTitle'))

useDockSuppression(() => open.value)

watch(open, (value) => {
  if (value && !dialog.value?.open) dialog.value?.showModal()
  if (!value && dialog.value?.open) dialog.value.close()
  if (value) errorText.value = ''
}, { flush: 'post' })

function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  errorText.value = ''
}

function validate(): string {
  if (mode.value === 'login') return form.account.trim() && form.password ? '' : t('auth.contactRequired')
  if (!form.email.trim() && !form.phone.trim()) return t('auth.contactRequired')
  if (form.password.length < 8) return t('auth.passwordHint')
  return ''
}

async function submit() {
  errorText.value = validate()
  if (errorText.value) return
  submitting.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(form.account.trim(), form.password)
      showToast(t('auth.loginSuccess'))
    } else {
      await auth.register({
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        username: form.username.trim() || form.email.trim() || form.phone.trim(),
        password: form.password,
      })
      showToast(t('auth.registerSuccess'))
    }
    form.password = ''
    open.value = false
  } catch (error) {
    errorText.value = error instanceof ApiError && error.status !== 0 ? error.message : t('common.error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="auth-dialog" aria-labelledby="auth-dialog-title" @close="open = false">
    <header class="auth-dialog__header">
      <h2 id="auth-dialog-title">{{ title }}</h2>
      <button type="button" class="auth-dialog__close" :aria-label="t('common.close')" @click="open = false"><X :size="20" aria-hidden="true" /></button>
    </header>
    <form class="auth-dialog__form" novalidate @submit.prevent="submit">
      <template v-if="mode === 'login'">
        <label>{{ t('auth.account') }}<input v-model="form.account" autocomplete="username" required /></label>
      </template>
      <template v-else>
        <label>{{ t('auth.email') }}<input v-model="form.email" type="email" autocomplete="email" /></label>
        <label>{{ t('auth.phone') }}<input v-model="form.phone" inputmode="numeric" autocomplete="tel" maxlength="11" /></label>
        <label>{{ t('auth.username') }}<input v-model="form.username" maxlength="30" autocomplete="nickname" /></label>
      </template>
      <label>{{ t('auth.password') }}
        <input v-model="form.password" type="password" :placeholder="mode === 'register' ? t('auth.passwordHint') : ''" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required />
      </label>
      <p v-if="errorText" class="auth-dialog__error" role="alert">{{ errorText }}</p>
      <button type="submit" class="auth-dialog__submit" :disabled="submitting">
        {{ submitting ? t('common.loading') : t(mode === 'login' ? 'auth.login' : 'auth.register') }}
      </button>
      <button type="button" class="auth-dialog__switch" @click="switchMode">
        {{ t(mode === 'login' ? 'auth.toRegister' : 'auth.toLogin') }}
      </button>
    </form>
  </dialog>
</template>

<style scoped>
.auth-dialog {
  width: min(420px, calc(100vw - 32px)); padding: 24px; margin: auto;
  border: 2px solid var(--rule-strong); border-radius: 12px;
  background: var(--paper-raised); color: var(--ink); box-shadow: 5px 5px 0 var(--shadow-hard);
}
.auth-dialog::backdrop { background: rgb(0 0 0 / .45); }
.auth-dialog__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.auth-dialog__header h2 { font-size: 22px; font-weight: 850; font-style: italic; }
.auth-dialog__close { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 8px; }
.auth-dialog__close:hover { background: var(--paper-muted); }
.auth-dialog__form { display: grid; gap: 14px; }
.auth-dialog__form label { display: grid; gap: 6px; font-size: 13px; font-weight: 700; color: var(--ink-secondary); }
.auth-dialog__form input {
  height: 44px; padding: 0 12px; border: 1.5px solid var(--rule-strong); border-radius: 8px;
  background: var(--paper); color: var(--ink); font-size: 15px;
}
.auth-dialog__form input:focus { outline: 2px solid var(--acid-strong); outline-offset: 1px; }
.auth-dialog__error { color: var(--danger, #c0392b); font-size: 13px; }
.auth-dialog__submit {
  height: 46px; border: 2px solid var(--rule-strong); border-radius: 8px;
  background: var(--acid); color: var(--acid-ink); font-size: 15px; font-weight: 850;
  box-shadow: 3px 3px 0 var(--shadow-hard); cursor: pointer;
}
.auth-dialog__submit:disabled { opacity: .6; cursor: progress; }
.auth-dialog__switch { justify-self: center; color: var(--ink-secondary); font-size: 13px; text-decoration: underline; }
</style>
