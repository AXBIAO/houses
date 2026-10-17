<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { useI18n } from 'vue-i18n'
import { LogIn, LogOut, UserRound } from 'lucide-vue-next'
import AppDock from '@/components/layout/AppDock.vue'
import LayoutFooter from '@/components/layout/LayoutFooter.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import LocaleToggle from '@/components/LocaleToggle.vue'
import PwaInstallLink from '@/components/PwaInstallLink.vue'
import AuthDialog from '@/components/auth/AuthDialog.vue'
import AccountDialog from '@/components/auth/AccountDialog.vue'
import NotificationBell from '@/components/NotificationBell.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { NAV_ITEMS, visibleNavItems } from '@/features/navigation/navigationModel'
import { useAuthDialog } from '@/composables/useAuthDialog'
import { dockSuppressed } from '@/composables/useDockSuppression'
import { showToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/authStore'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const isMobile = useMediaQuery('(max-width: 767px)')
const { open: authOpen } = useAuthDialog()
const accountOpen = ref(false)
const notifications = useNotificationStore()
// 登录后建立实时通知连接，退出时断开
watch(() => auth.user?.id ?? null, (id) => (id ? notifications.connect() : notifications.disconnect()), { immediate: true })
const navItems = computed(() => visibleNavItems(NAV_ITEMS, { isLandlord: auth.isLandlord, isPlatformAdmin: auth.isPlatformAdmin }))
// 有子路由的后台页面保持同一个外壳实例，只在切换顶级页面时重建；其余页面按完整路径重建
const viewKey = computed(() => {
  const record = route.matched[1]
  return record?.children.length ? record.path : route.path
})
const accountName = computed(() => auth.user?.username ?? '')

function openAuth() {
  authOpen.value = true
}
function logout() {
  auth.logout()
  showToast(t('auth.logoutSuccess'))
}
</script>

<template>
  <div class="houses-shell">
    <header class="masthead">
      <RouterLink to="/" class="masthead__brand" :aria-label="t('brand.name')">
        <span class="wordmark" aria-hidden="true">
          <span class="wordmark__zh">房子</span>
          <span class="wordmark__en">Houses</span>
        </span>
      </RouterLink>
      <p v-if="!isMobile" class="masthead__slogan">
        <span>{{ t('brand.slogan') }}</span>
        <span class="masthead__slogan-sep" aria-hidden="true">/</span>
        <span>{{ t('brand.sloganSecondary') }}</span>
      </p>
      <div class="masthead__actions">
        <PwaInstallLink v-if="!isMobile" />
        <NotificationBell v-if="auth.isLoggedIn" />
        <ThemeToggle />
        <LocaleToggle />
        <template v-if="!isMobile">
          <button v-if="auth.isLoggedIn" type="button" class="masthead__account" :title="t('navigation.accountSettings')" @click="accountOpen = true">
            <UserRound :size="16" aria-hidden="true" /><span>{{ accountName }}</span>
          </button>
          <button v-if="auth.isLoggedIn" type="button" class="masthead__logout" :title="t('navigation.logout')" :aria-label="t('navigation.logout')" @click="logout">
            <LogOut :size="16" aria-hidden="true" />
          </button>
          <button v-else type="button" class="masthead__account" @click="openAuth">
            <LogIn :size="16" aria-hidden="true" /><span>{{ t('navigation.loginAccount') }}</span>
          </button>
        </template>
      </div>
    </header>

    <main class="houses-main">
      <RouterView v-slot="{ Component }">
        <component :is="Component" :key="viewKey" />
      </RouterView>
    </main>

    <!-- 登录或角色变化会增减导航项；按项集合重建 Dock，让滑动指示器重新测量所有项 -->
    <AppDock
      :key="navItems.map(item => item.to).join('|')"
      v-show="!dockSuppressed"
      :items="navItems"
      :current-path="route.path"
      :is-logged-in="auth.isLoggedIn"
      @login="openAuth"
      @logout="logout"
      @account-settings="accountOpen = true"
    />
    <LayoutFooter />
    <AuthDialog v-model="authOpen" />
    <AccountDialog v-model="accountOpen" @logout="logout" />
  </div>
</template>

<style scoped>
.houses-shell { min-height: 100dvh; }
.masthead {
  position: sticky; top: 0; z-index: 90;
  display: flex; align-items: center; gap: 20px;
  height: 60px; padding: 0 clamp(16px, 3vw, 40px);
  border-bottom: 1.5px solid var(--rule-strong);
  background: var(--paper-raised);
}
.masthead__brand { display: inline-flex; align-items: center; text-decoration: none; color: var(--ink); }
.wordmark { position: relative; color: var(--acid-ink); display: inline-flex; align-items: baseline; gap: 6px; padding: 2px 10px 2px 6px; }
.wordmark::before {
  content: ''; position: absolute; inset: 4px 0 2px; z-index: -1;
  background: var(--acid); transform: skewX(-12deg); border-radius: 2px;
}
.wordmark__zh { font-size: 22px; font-weight: 900; letter-spacing: .04em; }
.wordmark__en { font-size: 15px; font-weight: 800; font-style: italic; letter-spacing: -.02em; }
.masthead__slogan { display: flex; align-items: center; gap: 10px; margin: 0; color: var(--ink-secondary); font-size: 14px; font-weight: 600; }
.masthead__slogan-sep { color: var(--ink-faint); }
.masthead__actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.masthead__account {
  display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 12px;
  border: 1.5px solid var(--rule-strong); border-radius: 999px;
  background: var(--paper); color: var(--ink); font-size: 13px; font-weight: 700;
  box-shadow: 2px 2px 0 var(--shadow-hard); cursor: pointer;
}
button.masthead__account:hover { background: var(--acid); color: var(--acid-ink); }
.masthead__account--static { cursor: default; box-shadow: none; }
.masthead__logout { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 999px; color: var(--danger, #c0392b); }
.masthead__logout:hover { background: var(--paper-muted); }
.houses-main { width: 100%; max-width: 1280px; margin: 0 auto; padding: 24px clamp(16px, 3vw, 40px) 140px; }
@media (max-width: 767px) {
  .masthead { height: 52px; gap: 12px; }
  .wordmark__zh { font-size: 19px; }
  .houses-main { padding-bottom: calc(96px + env(safe-area-inset-bottom)); }
}
</style>
