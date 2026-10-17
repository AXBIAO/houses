<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineOptions({ name: 'PrivacyView' })

const SECTIONS = ['collect', 'notCollect', 'location', 'local', 'thirdParty', 'security', 'rights'] as const
const { t } = useI18n()
</script>

<template>
  <article class="doc">
    <h1>{{ t('privacy.title') }}</h1>
    <p class="doc__meta">{{ t('privacy.updated') }}</p>
    <p>{{ t('privacy.intro') }}</p>
    <section v-for="key in SECTIONS" :key="key">
      <h2>{{ t(`privacy.${key}.title`) }}</h2>
      <p>{{ t(`privacy.${key}.body`) }}</p>
    </section>
  </article>
</template>

<style scoped>
.doc { display: grid; gap: 18px; max-width: 760px; margin: 0 auto; padding: 28px; border: 2px solid var(--rule-strong); border-radius: 18px; background: var(--paper-raised); box-shadow: 4px 4px 0 var(--shadow-hard); }
.doc h1 { font-size: clamp(28px, 4vw, 40px); font-weight: 900; font-style: italic; }
.doc__meta { color: var(--ink-muted); font-size: 13px; }
.doc h2 { margin-bottom: 6px; font-size: 18px; font-weight: 900; }
.doc p { color: var(--ink-secondary); line-height: 1.8; white-space: pre-line; }
</style>
