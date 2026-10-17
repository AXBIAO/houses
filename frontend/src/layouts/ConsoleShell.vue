<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Lock } from 'lucide-vue-next'
import '@/console.css'
import { useAuthStore } from '@/stores/authStore'
import { useAuthDialog } from '@/composables/useAuthDialog'

export interface ConsoleTab {
  to: string
  labelKey: string
  exact?: boolean
}

const props = defineProps<{ titleKey: string; tabs: readonly ConsoleTab[]; access: 'landlord' | 'platform' }>()
const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const authDialog = useAuthDialog()

const allowed = computed(() => (props.access === 'landlord' ? auth.isLandlord : auth.isPlatformAdmin))
const subtitle = computed(() => (props.access === 'landlord' ? auth.user?.landlord?.name ?? '' : ''))
const denyReason = computed(() => {
  if (props.access === 'platform') return t('console.needPlatform')
  return auth.user?.landlord && !auth.user.landlord.active ? t('console.landlordDisabled') : t('console.needLandlord')
})
const isActive = (tab: ConsoleTab) => (tab.exact ? route.path === tab.to : route.path.startsWith(tab.to))

onMounted(async () => {
  await auth.ensureInitialized()
  // 平台刚开通或停用房东时，本地登录态里的身份可能已过期
  if (auth.isLoggedIn) await auth.refresh().catch(() => undefined)
})
</script>

<template>
  <div class="console">
    <header class="console__head">
      <div>
        <h1>{{ t(titleKey) }}</h1>
        <p v-if="subtitle" class="console__sub">{{ subtitle }}</p>
      </div>
      <nav v-if="allowed" class="console__tabs" :aria-label="t(titleKey)">
        <RouterLink
          v-for="tab in tabs" :key="tab.to" :to="tab.to" class="console__tab"
          :class="{ 'is-active': isActive(tab) }" :aria-current="isActive(tab) ? 'page' : undefined"
        >{{ t(tab.labelKey) }}</RouterLink>
      </nav>
    </header>

    <p v-if="!auth.initialized" class="c-hint">{{ t('common.loading') }}</p>
    <section v-else-if="!auth.isLoggedIn" class="c-empty console__gate">
      <Lock :size="28" aria-hidden="true" />
      <p>{{ t('console.loginFirst') }}</p>
      <button type="button" class="c-btn c-btn--primary" @click="authDialog.show()">{{ t('navigation.loginAccount') }}</button>
    </section>
    <section v-else-if="!allowed" class="c-empty console__gate">
      <Lock :size="28" aria-hidden="true" />
      <p>{{ denyReason }}</p>
      <RouterLink to="/" class="c-btn">{{ t('common.backHome') }}</RouterLink>
    </section>
    <RouterView v-else v-slot="{ Component }">
      <component :is="Component" :key="route.path" />
    </RouterView>
  </div>
</template>

<style scoped>
.console__head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; }
.console__head h1 { font-size: clamp(24px, 3vw, 34px); font-weight: 900; font-style: italic; }
.console__sub { color: var(--ink-secondary); font-weight: 700; }
.console__tabs { display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; border: 1.5px solid var(--rule-strong); border-radius: 12px; background: var(--paper-raised); }
.console__tab { padding: 7px 14px; border-radius: 8px; color: var(--ink-secondary); font-size: 14px; font-weight: 800; }
.console__tab.is-active { background: var(--ink); color: var(--paper-raised); }
.console__gate { display: grid; justify-items: center; gap: 12px; }
</style>
