<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckCircle2, XCircle } from 'lucide-vue-next'
import { settingsApi, type LlmSettings, type ProbeResult, type SmtpSettings } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import { showToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/authStore'

defineOptions({ name: 'AdminSettings' })

/** 常见 OpenAI 兼容服务，点一下填好接口地址 */
const PRESETS = [
  { name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { name: '通义千问', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { name: 'Kimi', baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
] as const

const { t } = useI18n()
const auth = useAuthStore()
const llm = ref<LlmSettings | null>(null)
const smtp = ref<SmtpSettings | null>(null)
const llmForm = reactive({ baseUrl: '', model: '', timeout: 30, apiKey: '', clearKey: false })
const smtpForm = reactive({ host: '', port: 465, user: '', sender: '', useTls: true, password: '', clearPassword: false })
const testMail = ref(auth.user?.email ?? '')
const busy = ref<'' | 'llm' | 'smtp' | 'llmTest' | 'smtpTest'>('')
const llmResult = ref<ProbeResult | null>(null)
const smtpResult = ref<ProbeResult | null>(null)

function applyLlm(view: LlmSettings) {
  llm.value = view
  Object.assign(llmForm, { baseUrl: view.baseUrl, model: view.model, timeout: view.timeout, apiKey: '', clearKey: false })
}
function applySmtp(view: SmtpSettings) {
  smtp.value = view
  Object.assign(smtpForm, { host: view.host, port: view.port, user: view.user, sender: view.sender, useTls: view.useTls, password: '', clearPassword: false })
}

async function load() {
  try {
    const res = await settingsApi.get()
    applyLlm(res.llm)
    applySmtp(res.smtp)
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function run<T>(kind: typeof busy.value, action: () => Promise<T>): Promise<T | null> {
  busy.value = kind
  try {
    return await action()
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
    return null
  } finally {
    busy.value = ''
  }
}

async function saveLlm() {
  const apiKey = llmForm.clearKey ? '' : llmForm.apiKey.trim() || null
  const view = await run('llm', () => settingsApi.saveLlm({ baseUrl: llmForm.baseUrl.trim(), model: llmForm.model.trim(), timeout: Number(llmForm.timeout) || 30, apiKey }))
  if (view) {
    applyLlm(view)
    showToast(t('console.saved'))
  }
}
async function saveSmtp() {
  const password = smtpForm.clearPassword ? '' : smtpForm.password || null
  const view = await run('smtp', () => settingsApi.saveSmtp({
    host: smtpForm.host.trim(), port: Number(smtpForm.port) || 465, user: smtpForm.user.trim(), sender: smtpForm.sender.trim(), useTls: smtpForm.useTls, password,
  }))
  if (view) {
    applySmtp(view)
    showToast(t('console.saved'))
  }
}
async function testLlm() {
  llmResult.value = await run('llmTest', () => settingsApi.testLlm())
}
async function testSmtp() {
  smtpResult.value = await run('smtpTest', () => settingsApi.testSmtp(testMail.value.trim()))
}
function usePreset(preset: (typeof PRESETS)[number]) {
  llmForm.baseUrl = preset.baseUrl
  llmForm.model = preset.model
}

onMounted(load)
</script>

<template>
  <p v-if="!auth.isSuperAdmin" class="c-empty">{{ t('settings.superadminOnly') }}</p>
  <template v-else>
    <p class="c-hint">{{ t('settings.lead') }}</p>

    <form class="c-card block" novalidate @submit.prevent="saveLlm">
      <header class="block__head">
        <h2>{{ t('settings.llm.title') }}</h2>
        <span v-if="llm" class="c-badge" :data-tone="llm.enabled ? 'good' : 'muted'">{{ t(`settings.source.${llm.enabled ? llm.source : 'none'}`) }}</span>
      </header>
      <p class="c-hint">{{ t('settings.llm.hint') }}</p>
      <div class="presets">
        <span class="c-hint">{{ t('settings.llm.presets') }}</span>
        <button v-for="p in PRESETS" :key="p.name" type="button" class="c-btn c-btn--sm" @click="usePreset(p)">{{ p.name }}</button>
      </div>
      <div class="c-form-grid">
        <label class="c-field c-field--wide">{{ t('settings.llm.baseUrl') }}<input v-model="llmForm.baseUrl" class="c-input" placeholder="https://api.deepseek.com/v1" autocomplete="off" /></label>
        <label class="c-field">{{ t('settings.llm.model') }}<input v-model="llmForm.model" class="c-input" placeholder="deepseek-chat" autocomplete="off" /></label>
        <label class="c-field">{{ t('settings.llm.timeout') }}<input v-model.number="llmForm.timeout" class="c-input" type="number" min="3" max="120" /></label>
        <label class="c-field c-field--wide">{{ t('settings.llm.apiKey') }}
          <input
            v-model="llmForm.apiKey" class="c-input" type="password" autocomplete="new-password" :disabled="llmForm.clearKey"
            :placeholder="llm?.apiKeySet ? t('settings.keepSecret', { tail: llm.apiKeyTail }) : 'sk-...'"
          />
          <span v-if="llm?.apiKeySet" class="check"><input v-model="llmForm.clearKey" type="checkbox" /> {{ t('settings.clearSecret') }}</span>
        </label>
      </div>
      <div class="c-toolbar actions">
        <button type="button" class="c-btn" :disabled="busy !== ''" @click="testLlm">{{ busy === 'llmTest' ? t('common.loading') : t('settings.llm.test') }}</button>
        <button type="submit" class="c-btn c-btn--primary" :disabled="busy !== ''">{{ t('console.save') }}</button>
      </div>
      <p v-if="llmResult" class="result" :class="{ 'is-ok': llmResult.ok }" role="status">
        <CheckCircle2 v-if="llmResult.ok" :size="16" aria-hidden="true" /><XCircle v-else :size="16" aria-hidden="true" />
        {{ llmResult.message }}<template v-if="llmResult.filters"> · {{ JSON.stringify(llmResult.filters) }}</template>
      </p>
    </form>

    <form class="c-card block" novalidate @submit.prevent="saveSmtp">
      <header class="block__head">
        <h2>{{ t('settings.smtp.title') }}</h2>
        <span v-if="smtp" class="c-badge" :data-tone="smtp.enabled ? 'good' : 'muted'">{{ t(`settings.source.${smtp.enabled ? smtp.source : 'none'}`) }}</span>
      </header>
      <p class="c-hint">{{ t('settings.smtp.hint') }}</p>
      <div class="c-form-grid">
        <label class="c-field">{{ t('settings.smtp.host') }}<input v-model="smtpForm.host" class="c-input" placeholder="smtp.qq.com" autocomplete="off" /></label>
        <label class="c-field">{{ t('settings.smtp.port') }}<input v-model.number="smtpForm.port" class="c-input" type="number" min="1" max="65535" /></label>
        <label class="c-field">{{ t('settings.smtp.user') }}<input v-model="smtpForm.user" class="c-input" autocomplete="off" /></label>
        <label class="c-field">{{ t('settings.smtp.password') }}
          <input
            v-model="smtpForm.password" class="c-input" type="password" autocomplete="new-password" :disabled="smtpForm.clearPassword"
            :placeholder="smtp?.passwordSet ? t('settings.keepSecret', { tail: smtp.passwordTail }) : t('settings.smtp.passwordHint')"
          />
          <span v-if="smtp?.passwordSet" class="check"><input v-model="smtpForm.clearPassword" type="checkbox" /> {{ t('settings.clearSecret') }}</span>
        </label>
        <label class="c-field c-field--wide">{{ t('settings.smtp.sender') }}<input v-model="smtpForm.sender" class="c-input" placeholder="房子 Houses <noreply@hc.hk.cn>" /></label>
        <label class="c-field check-field"><span class="check"><input v-model="smtpForm.useTls" type="checkbox" /> {{ t('settings.smtp.useTls') }}</span></label>
      </div>
      <div class="c-toolbar actions">
        <input v-model="testMail" class="c-input test-mail" type="email" :placeholder="t('settings.smtp.testTo')" :aria-label="t('settings.smtp.testTo')" />
        <button type="button" class="c-btn" :disabled="busy !== '' || !testMail" @click="testSmtp">{{ busy === 'smtpTest' ? t('common.loading') : t('settings.smtp.test') }}</button>
        <button type="submit" class="c-btn c-btn--primary" :disabled="busy !== ''">{{ t('console.save') }}</button>
      </div>
      <p v-if="smtpResult" class="result" :class="{ 'is-ok': smtpResult.ok }" role="status">
        <CheckCircle2 v-if="smtpResult.ok" :size="16" aria-hidden="true" /><XCircle v-else :size="16" aria-hidden="true" />{{ smtpResult.message }}
      </p>
    </form>
  </template>
</template>

<style scoped>
.block { display: grid; gap: 12px; }
.block__head { display: flex; align-items: center; gap: 10px; }
.block__head h2 { margin: 0; }
.presets { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.check { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-secondary); font-size: 13px; font-weight: 700; }
.check-field { align-content: end; }
.actions { justify-content: flex-end; }
.test-mail { width: auto; min-width: 220px; }
.result { display: flex; align-items: flex-start; gap: 6px; padding: 10px 12px; border: 1.5px solid var(--danger, #c0392b); border-radius: 10px; color: var(--danger, #c0392b); font-size: 13px; overflow-wrap: anywhere; }
.result.is-ok { border-color: var(--acid-strong); color: var(--ink); background: var(--acid-soft); }
:root[data-theme='dark'] .result.is-ok { background: var(--paper-muted); }
</style>
