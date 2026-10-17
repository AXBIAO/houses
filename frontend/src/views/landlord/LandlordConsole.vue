<script setup lang="ts">
import ConsoleShell, { type ConsoleTab } from '@/layouts/ConsoleShell.vue'

const TABS: readonly ConsoleTab[] = [
  { to: '/landlord', labelKey: 'console.tabs.overview', exact: true },
  { to: '/landlord/listings', labelKey: 'console.tabs.listings' },
  { to: '/landlord/estates', labelKey: 'console.tabs.estates' },
  { to: '/landlord/leases', labelKey: 'console.tabs.leases' },
  { to: '/landlord/bills', labelKey: 'console.tabs.bills' },
  { to: '/landlord/inquiries', labelKey: 'console.tabs.inquiries' },
  { to: '/landlord/members', labelKey: 'console.tabs.members' },
  { to: '/landlord/settings', labelKey: 'console.tabs.settings' },
]
</script>

<template>
  <ConsoleShell title-key="navigation.landlord" :tabs="TABS" access="landlord" />
</template>
