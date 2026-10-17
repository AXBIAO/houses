<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BillStatus, LeaseStatus } from '@/features/console/leasingTypes'

const props = defineProps<{ lease?: LeaseStatus; bill?: BillStatus; overdue?: boolean }>()
const { t } = useI18n()

const LEASE_TONES: Record<LeaseStatus, string> = { pending: 'warn', active: 'good', expired: 'bad', checked_out: 'muted', void: 'muted' }
const BILL_TONES: Record<BillStatus, string> = { unpaid: 'warn', partial: 'warn', settled: 'good', void: 'muted' }

const view = computed(() => {
  if (props.lease) return { tone: LEASE_TONES[props.lease], label: t(`lease.status.${props.lease}`) }
  if (props.bill && props.overdue) return { tone: 'bad', label: t('lease.overdue') }
  const status = props.bill ?? 'unpaid'
  return { tone: BILL_TONES[status], label: t(`lease.billStatus.${status}`) }
})
</script>

<template>
  <span class="c-badge" :data-tone="view.tone">{{ view.label }}</span>
</template>
