<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Bell } from 'lucide-vue-next'
import { useNotificationStore } from '@/stores/notificationStore'

const { t } = useI18n()
const store = useNotificationStore()
</script>

<template>
  <RouterLink
    :to="{ path: '/subscriptions', query: { tab: 'inbox' } }" class="bell"
    :aria-label="store.unread ? t('subs.unreadN', { n: store.unread }) : t('subs.inbox')"
    :title="store.unread ? t('subs.unreadN', { n: store.unread }) : t('subs.inbox')"
  >
    <Bell :size="18" aria-hidden="true" />
    <span v-if="store.unread" class="bell__badge">{{ store.unread > 99 ? '99+' : store.unread }}</span>
    <span v-if="store.connected" class="bell__live" aria-hidden="true" />
  </RouterLink>
</template>

<style scoped>
.bell { position: relative; display: grid; place-items: center; width: 34px; height: 34px; border-radius: 999px; color: var(--ink); }
.bell:hover { background: var(--paper-muted); }
.bell__badge { position: absolute; top: -2px; right: -4px; min-width: 18px; height: 18px; padding: 0 5px; border: 1.5px solid var(--paper-raised); border-radius: 999px; background: var(--danger, #d64c3b); color: #fff; font-size: 11px; font-weight: 800; line-height: 15px; text-align: center; }
.bell__live { position: absolute; bottom: 4px; right: 5px; width: 6px; height: 6px; border-radius: 50%; background: var(--acid-strong); }
</style>
