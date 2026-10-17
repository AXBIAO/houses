<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ExternalLink } from 'lucide-vue-next'
import BlockManager from '@/components/console/BlockManager.vue'
import ImageManager from '@/components/console/ImageManager.vue'
import ListingStatusBadge from '@/components/console/ListingStatusBadge.vue'
import TagInput from '@/components/console/TagInput.vue'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import { emptyListingForm, formFromDetail, toListingInput, type ListingForm } from '@/features/console/listingForm'
import type { ConsoleListingDetail, Estate } from '@/features/console/types'
import { RENT_TYPES } from '@/features/listings/types'
import { showToast } from '@/composables/useToast'

defineOptions({ name: 'ListingEditor' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const listingId = computed(() => (route.params.id === 'new' ? null : Number(route.params.id)))
const estates = ref<Estate[]>([])
const detail = ref<ConsoleListingDetail | null>(null)
const form = ref<ListingForm>(emptyListingForm(null))
const loading = ref(true)
const saving = ref(false)
const errorText = ref('')
const isShort = computed(() => form.value.rentType === 'short')

async function load() {
  loading.value = true
  try {
    estates.value = (await landlordApi.estates()).items
    if (listingId.value) {
      detail.value = await landlordApi.listing(listingId.value)
      form.value = formFromDetail(detail.value)
    } else {
      form.value = emptyListingForm(estates.value[0]?.id ?? null)
    }
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    loading.value = false
  }
}

async function save(publishAfter: boolean) {
  const result = toListingInput(form.value)
  if ('errorKey' in result) {
    errorText.value = t(result.errorKey)
    return
  }
  errorText.value = ''
  saving.value = true
  try {
    let saved = listingId.value
      ? await landlordApi.updateListing(listingId.value, result.input)
      : await landlordApi.createListing(result.input)
    if (publishAfter && saved.status !== 'published') saved = await landlordApi.setStatus(saved.id, 'published')
    detail.value = saved
    form.value = formFromDetail(saved)
    showToast(t(publishAfter ? 'console.published' : 'console.saved'))
    if (!listingId.value) await router.replace(`/landlord/listings/${saved.id}`)
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

async function takeDown() {
  if (!detail.value) return
  try {
    detail.value = await landlordApi.setStatus(detail.value.id, 'offline')
    showToast(t('console.offlined'))
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

onMounted(load)
</script>

<template>
  <p v-if="loading" class="c-hint">{{ t('common.loading') }}</p>
  <div v-else-if="!estates.length && !detail" class="c-empty">
    <p>{{ t('console.needEstateFirst') }}</p>
    <RouterLink to="/landlord/estates" class="c-btn c-btn--primary">{{ t('console.manageEstates') }}</RouterLink>
  </div>
  <template v-else>
    <div class="c-toolbar">
      <RouterLink to="/landlord/listings" class="c-btn c-btn--sm">← {{ t('console.tabs.listings') }}</RouterLink>
      <h2 class="c-section-title editor-title">{{ detail ? detail.title : t('console.newListing') }}</h2>
      <ListingStatusBadge v-if="detail" :status="detail.status" />
      <a v-if="detail?.status === 'published'" :href="`/listings/${detail.id}`" target="_blank" rel="noopener" class="c-btn c-btn--sm">
        <ExternalLink :size="14" aria-hidden="true" />{{ t('console.viewPublic') }}
      </a>
    </div>

    <form class="c-card" novalidate @submit.prevent="save(false)">
      <h2>{{ t('console.basicInfo') }}</h2>
      <div class="c-form-grid">
        <label class="c-field">{{ t('console.field.rentType') }}
          <select v-model="form.rentType" class="c-select">
            <option v-for="type in RENT_TYPES" :key="type" :value="type">{{ t(`rentType.${type}`) }}</option>
          </select>
        </label>
        <label class="c-field">{{ t('console.field.estate') }}
          <select v-model.number="form.estateId" class="c-select">
            <option v-for="e in estates" :key="e.id" :value="e.id">{{ e.name }}（{{ e.district }}）</option>
          </select>
        </label>
        <label class="c-field">{{ t('console.field.building') }}<input v-model="form.building" class="c-input" maxlength="20" /></label>
        <label class="c-field">{{ t('console.field.unitNo') }}<input v-model="form.unitNo" class="c-input" maxlength="20" /></label>
        <label class="c-field c-field--wide">{{ t('console.field.title') }}<input v-model="form.title" class="c-input" maxlength="80" required /></label>
        <label class="c-field c-field--wide">{{ t('console.field.description') }}<textarea v-model="form.description" class="c-textarea" rows="4" maxlength="2000" /></label>
      </div>

      <h2 class="form-section">{{ t('console.layoutInfo') }}</h2>
      <div class="c-form-grid">
        <label class="c-field">{{ t('console.field.bedrooms') }}<input v-model.number="form.bedrooms" class="c-input" type="number" min="0" max="20" /></label>
        <label class="c-field">{{ t('console.field.halls') }}<input v-model.number="form.halls" class="c-input" type="number" min="0" max="10" /></label>
        <label class="c-field">{{ t('console.field.baths') }}<input v-model.number="form.baths" class="c-input" type="number" min="0" max="10" /></label>
        <label class="c-field">{{ t('console.field.area') }}<input v-model.number="form.area" class="c-input" type="number" min="1" step="0.1" required /></label>
        <label class="c-field">{{ t('console.field.floor') }}<input v-model.number="form.floor" class="c-input" type="number" /></label>
        <label class="c-field">{{ t('console.field.totalFloors') }}<input v-model.number="form.totalFloors" class="c-input" type="number" min="1" /></label>
        <label class="c-field">{{ t('console.field.orientation') }}<input v-model="form.orientation" class="c-input" maxlength="10" :placeholder="t('console.orientationHint')" /></label>
      </div>

      <h2 class="form-section">{{ t('console.priceInfo') }}</h2>
      <div class="c-form-grid">
        <label v-if="isShort" class="c-field">{{ t('console.field.priceNight') }}<input v-model.number="form.priceNight" class="c-input" type="number" min="1" required /></label>
        <label v-else class="c-field">{{ t('console.field.priceMonth') }}<input v-model.number="form.priceMonth" class="c-input" type="number" min="1" required /></label>
        <label v-if="!isShort" class="c-field">{{ t('console.field.depositMonths') }}<input v-model.number="form.depositMonths" class="c-input" type="number" min="0" max="12" /></label>
        <label v-if="isShort" class="c-field">{{ t('console.field.minNights') }}<input v-model.number="form.minNights" class="c-input" type="number" min="1" max="365" /></label>
        <label v-else class="c-field">{{ t('console.field.minMonths') }}<input v-model.number="form.minMonths" class="c-input" type="number" min="1" max="60" /></label>
        <label class="c-field">{{ t('console.field.availableFrom') }}<input v-model="form.availableFrom" class="c-input" type="date" /></label>
      </div>

      <h2 class="form-section">{{ t('filters.tags') }}</h2>
      <TagInput v-model="form.tags" />

      <p v-if="errorText" class="c-error form-error" role="alert">{{ errorText }}</p>
      <div class="c-toolbar form-actions">
        <button type="submit" class="c-btn" :disabled="saving">{{ t('console.save') }}</button>
        <button v-if="detail?.status !== 'published'" type="button" class="c-btn c-btn--primary" :disabled="saving" @click="save(true)">{{ t('console.saveAndPublish') }}</button>
        <button v-else type="button" class="c-btn" :disabled="saving" @click="takeDown">{{ t('console.offline') }}</button>
      </div>
    </form>

    <template v-if="detail">
      <ImageManager v-model="detail.images" :listing-id="detail.id" />
      <BlockManager v-model="detail.unavailable" :listing-id="detail.id" />
    </template>
    <p v-else class="c-hint">{{ t('console.saveFirstHint') }}</p>
  </template>
</template>

<style scoped>
.editor-title { margin: 0; }
.form-section { margin-top: 20px; }
.form-error { margin-top: 14px; }
.form-actions { margin-top: 18px; justify-content: flex-end; }
</style>
