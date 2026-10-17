<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

defineOptions({ name: 'PlaceholderView' })

const route = useRoute()
const { t } = useI18n()
const title = computed(() => t(String(route.meta.titleKey ?? 'pages.notFound')))
const isNotFound = computed(() => route.name === 'not-found')
</script>

<template>
  <section class="placeholder">
    <h1>{{ title }}</h1>
    <p>{{ isNotFound ? t('pages.notFoundDesc') : t('common.comingSoon') }}</p>
    <RouterLink to="/" class="placeholder__back">{{ t('common.backHome') }}</RouterLink>
  </section>
</template>

<style scoped>
.placeholder { display: grid; justify-items: start; gap: 12px; max-width: 640px; margin: 48px auto; padding: 28px; border: 2px solid var(--rule-strong); border-radius: 16px; background: var(--paper-raised); box-shadow: 4px 4px 0 var(--shadow-hard); }
.placeholder h1 { font-size: 28px; font-weight: 900; font-style: italic; }
.placeholder p { color: var(--ink-secondary); }
.placeholder__back { padding: 8px 16px; border: 1.5px solid var(--rule-strong); border-radius: 999px; background: var(--acid); color: var(--acid-ink); font-weight: 800; }
</style>
