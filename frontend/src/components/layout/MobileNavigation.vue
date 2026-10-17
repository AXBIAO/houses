<script setup lang="ts">
// Modified for Houses (based on AIGCNEWS, AGPL-3.0)
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Menu, X, UserRound, LogOut } from 'lucide-vue-next'
import PwaInstallLink from '@/components/PwaInstallLink.vue'
import LayoutFooter from './LayoutFooter.vue'
import { isNavigationItemActive, type NavigationItem } from '@/features/navigation/navigationModel'
import { vIndicator } from '@/motion/indicator'

const props = defineProps<{
  items: readonly NavigationItem[]
  currentPath: string
  isLoggedIn: boolean
}>()
const emit = defineEmits<{ login: []; logout: []; accountSettings: [] }>()
const { t } = useI18n()
const dialog = ref<HTMLDialogElement>()
const menuButton = ref<HTMLButtonElement>()
const menuOpen = ref(false)
const accessibleItems = computed(() => props.items)
const primaryItems = computed(() => accessibleItems.value.filter(item => item.primary))
const secondaryItems = computed(() => accessibleItems.value.filter(item => !item.primary))
const isActive = (item: NavigationItem) => isNavigationItemActive(item, props.currentPath)
const moreActive = computed(() => secondaryItems.value.some(isActive))

function openMenu() {
  menuButton.value?.focus()
  dialog.value?.showModal()
  menuOpen.value = true
}
function closeMenu() {
  dialog.value?.close()
  menuOpen.value = false
}
function accountAction(action: 'login' | 'logout' | 'accountSettings') {
  closeMenu()
  if (action === 'login') emit('login')
  else if (action === 'logout') emit('logout')
  else emit('accountSettings')
}
watch([() => props.currentPath, () => props.isLoggedIn], closeMenu)
onBeforeUnmount(closeMenu)
</script>

<template>
  <nav v-indicator="{ active: '.mobile-nav__item.is-active', follow: 'a.mobile-nav__item' }" class="mobile-nav" :aria-label="t('navigation.primary')">
    <RouterLink
      v-for="item in primaryItems" :key="item.to" :to="item.to"
      class="mobile-nav__item" :class="{ 'is-active': isActive(item) }"
      :aria-current="isActive(item) ? 'page' : undefined"
    >
      <span class="mobile-nav__icon" aria-hidden="true" v-html="item.icon" />
      <span>{{ t(item.captionKey) }}</span>
    </RouterLink>
    <button
      ref="menuButton" type="button" class="mobile-nav__item"
      :class="{ 'is-active': moreActive || menuOpen }"
      aria-haspopup="dialog" :aria-expanded="menuOpen" @click="openMenu"
    >
      <Menu class="mobile-nav__icon" aria-hidden="true" />
      <span>{{ t('navigation.more') }}</span>
    </button>

    <Teleport to="body">
      <dialog ref="dialog" class="mobile-menu" aria-labelledby="mobile-menu-title" @close="menuOpen = false" @click.self="closeMenu">
        <div class="mobile-menu__content">
          <header class="mobile-menu__header">
            <h2 id="mobile-menu-title">{{ t('navigation.more') }}</h2>
            <button type="button" :aria-label="t('common.close')" autofocus @click="closeMenu"><X aria-hidden="true" /></button>
          </header>
          <div class="mobile-menu__links">
            <RouterLink
              v-for="item in secondaryItems" :key="item.to" :to="item.to"
              class="mobile-menu__link" :class="{ 'is-active': isActive(item) }"
              :aria-current="isActive(item) ? 'page' : undefined" @click="closeMenu"
            >
              <span class="mobile-nav__icon" aria-hidden="true" v-html="item.icon" />
              <span>{{ t(item.labelKey) }}</span>
            </RouterLink>
          </div>
          <div class="mobile-menu__account">
            <button v-if="!isLoggedIn" type="button" @click="accountAction('login')"><UserRound aria-hidden="true" />{{ t('navigation.loginAccount') }}</button>
            <template v-else>
              <button type="button" @click="accountAction('accountSettings')"><UserRound aria-hidden="true" />{{ t('navigation.accountSettings') }}</button>
              <button type="button" @click="accountAction('logout')"><LogOut aria-hidden="true" />{{ t('navigation.logout') }}</button>
            </template>
          </div>
          <div class="mobile-menu__utilities"><PwaInstallLink @click="closeMenu" /></div>
          <LayoutFooter embedded />
        </div>
      </dialog>
    </Teleport>
  </nav>
</template>

<style scoped>
/* The opaque bottom bar covers the safe area so scrolling content cannot show around the dock. */
.mobile-nav { position: fixed; z-index: 100; inset: auto 0 0; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 2px; padding: 6px max(8px, env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left)); background: var(--dock-surface); border: 0; border-top: 1.5px solid var(--dock-edge); }
.mobile-nav__item { position: relative; display: flex; min-width: 0; min-height: 50px; flex-direction: column; align-items: center; justify-content: center; gap: 4px; border-radius: 6px; color: var(--dock-text); font-size: 11px; font-weight: 600; line-height: 1.3; text-decoration: none; }
.mobile-nav__item > span { max-width: 100%; overflow-wrap: anywhere; text-align: center; }
.mobile-nav__item.is-active { color: var(--acid-ink); background: var(--acid); }
/* 选中底色由 v-indicator 画在导航条的 ::before 上滑动；打开「更多」时滑到菜单键，关上再滑回来。 */
.mobile-nav::before { z-index: -1; border-radius: 6px; background: var(--acid); }
.mobile-nav__item { transition: color 160ms ease; }
.mobile-nav[data-indicator] .mobile-nav__item.is-active { background: transparent; transition-delay: 70ms; }
.mobile-nav[data-indicator-pending] .mobile-nav__item.is-active { color: var(--dock-text); transition-delay: 0ms; }
.mobile-nav .mobile-nav__item[data-indicator-target] { color: var(--acid-ink); transition-delay: 70ms; }
.mobile-nav__item:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
.mobile-nav__icon { display: inline-flex; flex: 0 0 20px; width: 20px; height: 20px; }
.mobile-nav__icon :deep(svg) { width: 20px; height: 20px; }
.mobile-nav__alert, .mobile-menu__alert { width: 8px; height: 8px; border-radius: 50%; background: var(--error-accent); }
.mobile-nav__alert { position: absolute; top: 6px; right: 20%; }
.mobile-menu { position: fixed; inset: auto 0 0; width: 100%; max-width: 40rem; max-height: calc(100dvh - 24px); margin: 0 auto; padding: 0; overflow-y: auto; overscroll-behavior: contain; color: var(--ink); background: var(--paper-raised); border: 1px solid var(--rule-strong); border-radius: 16px 16px 0 0; }
.mobile-menu::backdrop { background: var(--overlay-backdrop, rgb(0 0 0 / 0.45)); }
.mobile-menu__content { padding: 16px 16px max(16px, env(safe-area-inset-bottom)); }
.mobile-menu__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.mobile-menu__header h2 { font-size: 20px; font-weight: 700; }
.mobile-menu__header button { display: grid; width: 44px; height: 44px; place-items: center; }
.mobile-menu__links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.mobile-menu__link { display: flex; min-width: 0; min-height: 52px; align-items: center; gap: 10px; padding: 12px; border: 1px solid var(--rule); border-radius: 6px; font-size: 14px; overflow-wrap: anywhere; }
.mobile-menu__link.is-active { background: var(--acid-soft); border-color: var(--ink); }
.mobile-menu__account { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--rule); }
.mobile-menu__account button { display: flex; min-height: 44px; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--rule); border-radius: 6px; font-size: 14px; }
.mobile-menu__account svg { width: 18px; height: 18px; }
.mobile-menu__footer { display: flex; flex-wrap: wrap; gap: 0 16px; margin-top: 16px; color: var(--ink-muted); font-size: 12px; }
.mobile-menu__footer a { display: inline-flex; min-height: 44px; align-items: center; }
.mobile-menu__utilities { display: flex; gap: 12px; margin-top: 16px; }
.mobile-menu__utilities :deep(button), .mobile-menu__utilities :deep(a) { min-width: 44px; min-height: 44px; }
.mobile-menu { border-width:2px;border-radius:12px 12px 0 0; }
.mobile-menu__link { border-color:var(--rule-strong);background:var(--paper); }
.mobile-menu__link.is-active { color:var(--acid-ink);background:var(--acid);border-color:var(--rule-strong); }
.mobile-menu__header h2 { font-style:italic;font-weight:850; }
</style>
