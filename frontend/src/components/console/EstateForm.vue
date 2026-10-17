<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import LeafletMap from '@/components/map/LeafletMap.vue'
import type { Estate, EstateInput } from '@/features/console/types'

const DEFAULT_POINT = { lat: 30.6598, lng: 104.0657 }

const props = defineProps<{ estate: Estate | null; saving: boolean; errorText: string }>()
const emit = defineEmits<{ submit: [input: EstateInput]; cancel: [] }>()
const { t } = useI18n()

const form = reactive<EstateInput>(props.estate
  ? { name: props.estate.name, city: props.estate.city, district: props.estate.district, address: props.estate.address, lat: props.estate.lat, lng: props.estate.lng }
  : { name: '', city: '成都', district: '', address: '', ...DEFAULT_POINT })
const picked = ref(props.estate !== null)
const localError = ref('')
const center = computed<[number, number]>(() => [form.lat, form.lng])
const marker = computed(() => (picked.value ? [{ id: 0, lat: form.lat, lng: form.lng, label: form.name || t('console.location') }] : []))

function pick(lat: number, lng: number) {
  form.lat = Number(lat.toFixed(6))
  form.lng = Number(lng.toFixed(6))
  picked.value = true
}

function submit() {
  localError.value = ''
  if (!form.name.trim() || !form.city.trim() || !form.district.trim()) {
    localError.value = t('console.errors.estateFields')
    return
  }
  if (!picked.value) {
    localError.value = t('console.errors.pickLocation')
    return
  }
  emit('submit', { ...form, name: form.name.trim(), city: form.city.trim(), district: form.district.trim(), address: form.address.trim() })
}
</script>

<template>
  <form class="c-card estate-form" novalidate @submit.prevent="submit">
    <h2>{{ estate ? t('console.editEstate') : t('console.newEstate') }}</h2>
    <div class="estate-form__body">
      <div class="c-form-grid">
        <label class="c-field">{{ t('console.field.estateName') }}<input v-model="form.name" class="c-input" maxlength="40" required /></label>
        <label class="c-field">{{ t('console.field.city') }}<input v-model="form.city" class="c-input" maxlength="20" required /></label>
        <label class="c-field">{{ t('filters.district') }}<input v-model="form.district" class="c-input" maxlength="20" required /></label>
        <label class="c-field c-field--wide">{{ t('console.field.address') }}<input v-model="form.address" class="c-input" maxlength="120" /></label>
        <p class="c-hint c-field--wide">{{ picked ? t('console.pickedAt', { lat: form.lat, lng: form.lng }) : t('console.pickHint') }}</p>
      </div>
      <div class="estate-form__map">
        <LeafletMap :center="center" :zoom="13" :markers="marker" :active-id="0" @pick="pick" />
      </div>
    </div>
    <p v-if="localError || errorText" class="c-error" role="alert">{{ localError || errorText }}</p>
    <div class="c-toolbar estate-form__actions">
      <button type="button" class="c-btn" @click="emit('cancel')">{{ t('common.cancel') }}</button>
      <button type="submit" class="c-btn c-btn--primary" :disabled="saving">{{ t('console.save') }}</button>
    </div>
  </form>
</template>

<style scoped>
.estate-form__body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
.estate-form__map { height: 300px; overflow: hidden; border: 1.5px solid var(--rule-strong); border-radius: 12px; }
.estate-form__actions { justify-content: flex-end; margin-top: 12px; }
@media (max-width: 860px) { .estate-form__body { grid-template-columns: 1fr; } }
</style>
