<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSiteInfo } from '@/composables/useSiteInfo'

defineOptions({ name: 'AboutView' })

const SECTIONS = ['what', 'renters', 'landlords', 'money', 'openSource'] as const
const { t } = useI18n()
const site = useSiteInfo()
</script>

<template>
  <article class="doc">
    <h1>{{ t('about.title') }}</h1>
    <p class="doc__lead">{{ t('brand.slogan') }} · {{ t('brand.sloganSecondary') }}</p>
    <section v-for="key in SECTIONS" :key="key">
      <h2>{{ t(`about.${key}.title`) }}</h2>
      <p>{{ t(`about.${key}.body`) }}</p>
    </section>
    <p class="doc__source">
      {{ t('about.sourceLabel') }}
      <a :href="site.sourceCodeUrl" target="_blank" rel="noopener noreferrer">{{ site.sourceCodeUrl }}</a>
    </p>
    <RouterLink to="/privacy" class="doc__link">{{ t('footer.privacy') }} →</RouterLink>
  </article>
</template>

<style scoped>
.doc { display: grid; gap: 18px; max-width: 760px; margin: 0 auto; padding: 28px; border: 2px solid var(--rule-strong); border-radius: 18px; background: var(--paper-raised); box-shadow: 4px 4px 0 var(--shadow-hard); }
.doc h1 { font-size: clamp(28px, 4vw, 40px); font-weight: 900; font-style: italic; }
.doc__lead { color: var(--ink-secondary); font-weight: 800; }
.doc h2 { margin-bottom: 6px; font-size: 18px; font-weight: 900; }
.doc p { color: var(--ink-secondary); line-height: 1.8; }
.doc__source a, .doc__link { color: var(--ink); font-weight: 800; text-decoration: underline; overflow-wrap: anywhere; }
</style>
