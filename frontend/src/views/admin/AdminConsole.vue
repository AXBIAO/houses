<script setup lang="ts">
import { computed } from 'vue'
import ConsoleShell, { type ConsoleTab } from '@/layouts/ConsoleShell.vue'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()
// 系统设置涉及大模型与邮件密钥，只给超级管理员
const tabs = computed<ConsoleTab[]>(() => [
  { to: '/admin', labelKey: 'console.tabs.landlords', exact: true },
  { to: '/admin/listings', labelKey: 'console.tabs.moderation' },
  ...(auth.isSuperAdmin ? [{ to: '/admin/settings', labelKey: 'console.tabs.systemSettings' }] : []),
])
</script>

<template>
  <ConsoleShell title-key="navigation.admin" :tabs="tabs" access="platform" />
</template>
