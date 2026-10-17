<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ListingStatus } from '@/features/console/types'

defineProps<{ status: ListingStatus }>()
const { t } = useI18n()
const TONES: Record<ListingStatus, string> = { published: 'good', draft: 'warn', offline: 'muted' }
</script>

<template>
  <span class="c-badge" :data-tone="TONES[status]">{{ t(`console.status.${status}`) }}</span>
</template>
