<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckCircle2 } from 'lucide-vue-next'
import { listingsApi } from '@/features/listings/api'
import { ApiError } from '@/services/http/apiClient'
import { useAuthStore } from '@/stores/authStore'

const props = defineProps<{ listingId: number; isShort: boolean; moveIn?: string; moveOut?: string }>()
const { t } = useI18n()
const auth = useAuthStore()

const PHONE_RE = /^1\d{10}$/
const form = reactive({
  name: auth.user?.username ?? '',
  phone: auth.user?.phone ?? '',
  message: '',
  moveIn: props.moveIn ?? '',
  moveOut: props.moveOut ?? '',
})
const submitting = ref(false)
const sent = ref(false)
const errorText = ref('')
const today = new Date().toISOString().slice(0, 10)

function validate(): string {
  if (!form.name.trim()) return t('inquiry.nameRequired')
  if (!PHONE_RE.test(form.phone.trim())) return t('inquiry.phoneInvalid')
  if (form.moveIn && form.moveOut && form.moveOut <= form.moveIn) return t('inquiry.dateInvalid')
  return ''
}

async function submit() {
  errorText.value = validate()
  if (errorText.value) return
  submitting.value = true
  try {
    await listingsApi.inquire(props.listingId, {
      name: form.name.trim(),
      phone: form.phone.trim(),
      message: form.message.trim(),
      moveIn: form.moveIn || null,
      moveOut: props.isShort ? form.moveOut || null : null,
    })
    sent.value = true
  } catch (error) {
    errorText.value = error instanceof ApiError && error.status !== 0 && error.status < 500 ? error.message : t('common.error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="sent" class="inquiry inquiry--sent" role="status">
    <CheckCircle2 :size="28" aria-hidden="true" />
    <p><strong>{{ t('inquiry.sentTitle') }}</strong></p>
    <p>{{ t('inquiry.sentDesc') }}</p>
  </div>
  <form v-else class="inquiry" novalidate @submit.prevent="submit">
    <h2>{{ t('listing.contact') }}</h2>
    <label>{{ t('inquiry.name') }}<input v-model="form.name" maxlength="20" autocomplete="name" required /></label>
    <label>{{ t('inquiry.phone') }}<input v-model="form.phone" inputmode="numeric" maxlength="11" autocomplete="tel" required /></label>
    <div class="inquiry__dates">
      <label>{{ t('home.moveIn') }}<input v-model="form.moveIn" type="date" :min="today" /></label>
      <label v-if="isShort">{{ t('home.moveOut') }}<input v-model="form.moveOut" type="date" :min="form.moveIn || today" /></label>
    </div>
    <label>{{ t('inquiry.message') }}<textarea v-model="form.message" rows="3" maxlength="500" :placeholder="t('inquiry.messagePlaceholder')" /></label>
    <p v-if="errorText" class="inquiry__error" role="alert">{{ errorText }}</p>
    <button type="submit" class="inquiry__submit" :disabled="submitting">{{ submitting ? t('common.loading') : t('inquiry.submit') }}</button>
    <p class="inquiry__note">{{ t('inquiry.privacy') }}</p>
  </form>
</template>

<style scoped>
.inquiry { display: grid; gap: 12px; padding: 18px; border: 2px solid var(--rule-strong); border-radius: 16px; background: var(--paper-raised); box-shadow: 4px 4px 0 var(--shadow-hard); }
.inquiry h2 { font-size: 18px; font-weight: 900; }
.inquiry label { display: grid; gap: 5px; color: var(--ink-secondary); font-size: 13px; font-weight: 700; }
.inquiry input, .inquiry textarea { padding: 9px 10px; border: 1.5px solid var(--rule-strong); border-radius: 8px; background: var(--paper); color: var(--ink); font: inherit; font-size: 14px; }
.inquiry textarea { resize: vertical; }
.inquiry__dates { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; }
.inquiry__error { color: var(--danger, #c0392b); font-size: 13px; }
.inquiry__submit { height: 44px; border: 2px solid var(--rule-strong); border-radius: 10px; background: var(--acid); color: var(--acid-ink); font-size: 15px; font-weight: 900; box-shadow: 2px 2px 0 var(--shadow-hard); cursor: pointer; }
.inquiry__submit:disabled { opacity: .6; cursor: progress; }
.inquiry__note { color: var(--ink-muted); font-size: 12px; }
.inquiry--sent { justify-items: center; text-align: center; color: var(--ink); }
.inquiry--sent p { color: var(--ink-secondary); }
</style>
