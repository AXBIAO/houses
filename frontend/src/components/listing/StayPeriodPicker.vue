<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CalendarRange } from 'lucide-vue-next'
import { LEASE_MONTH_OPTIONS, type RentType } from '@/features/listings/types'

/** 租期：短租选入住/退房日期；长租、合租选入住日 + 租多久，用于匹配那段时间可租的房源。 */
const props = defineProps<{ rentType: RentType | null }>()
const moveIn = defineModel<string>('moveIn', { required: true })
const moveOut = defineModel<string>('moveOut', { required: true })
const months = defineModel<number | null>('months', { required: true })
const { t } = useI18n()

const today = new Date().toISOString().slice(0, 10)
const isShort = computed(() => props.rentType === 'short')

function pickMonths(m: number) {
  months.value = months.value === m ? null : m
}
function onMoveIn(value: string) {
  moveIn.value = value
  if (moveOut.value && value && moveOut.value <= value) moveOut.value = ''
}
</script>

<template>
  <div class="stay">
    <span class="stay__label"><CalendarRange :size="16" aria-hidden="true" />{{ t('home.stayPeriod') }}</span>
    <label class="stay__date">{{ t('home.moveIn') }}
      <input :value="moveIn" type="date" :min="today" @change="onMoveIn(($event.target as HTMLInputElement).value)" />
    </label>
    <label v-if="isShort" class="stay__date">{{ t('home.moveOut') }}
      <input v-model="moveOut" type="date" :min="moveIn || today" />
    </label>
    <div v-else class="stay__months" role="group" :aria-label="t('home.stayPeriod')">
      <button
        v-for="m in LEASE_MONTH_OPTIONS" :key="m" type="button" class="chip"
        :class="{ 'is-active': months === m }" :aria-pressed="months === m" @click="pickMonths(m)"
      >{{ t('home.months', { n: m }) }}</button>
    </div>
  </div>
</template>

<style scoped>
.stay { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 10px; }
.stay__label { display: inline-flex; align-items: center; gap: 6px; margin-right: 4px; color: var(--ink-secondary); font-size: 13px; font-weight: 800; }
.stay__date { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-secondary); font-size: 13px; }
.stay__date input { height: 34px; padding: 0 8px; border: 1.5px solid var(--rule-strong); border-radius: 8px; background: var(--paper); color: var(--ink); font-size: 13px; }
.stay__months { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { height: 32px; padding: 0 12px; border: 1.5px solid var(--rule); border-radius: 999px; background: var(--paper); color: var(--ink-secondary); font-size: 13px; font-weight: 700; cursor: pointer; }
.chip.is-active { border-color: var(--rule-strong); background: var(--acid); color: var(--acid-ink); }
</style>
