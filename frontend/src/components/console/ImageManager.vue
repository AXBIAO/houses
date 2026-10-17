<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, ArrowRight, ImagePlus, Trash2 } from 'lucide-vue-next'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { ListingImage } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

const MAX_IMAGES = 12
const MAX_BYTES = 5 * 1024 * 1024
const ACCEPT = 'image/jpeg,image/png,image/webp'

const props = defineProps<{ listingId: number }>()
const images = defineModel<ListingImage[]>({ required: true })
const { t } = useI18n()
const uploading = ref(false)
const input = ref<HTMLInputElement | null>(null)

async function onFiles(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files ?? [])
  ;(event.target as HTMLInputElement).value = ''
  const room = MAX_IMAGES - images.value.length
  if (files.length > room) showToast(t('console.imageLimit', { n: MAX_IMAGES }))
  uploading.value = true
  try {
    for (const file of files.slice(0, room)) {
      if (file.size > MAX_BYTES) {
        showToast(t('console.imageTooLarge', { name: file.name }))
        continue
      }
      try {
        const image = await landlordApi.uploadImage(props.listingId, file)
        images.value = [...images.value, image]
      } catch (error) {
        showToast(errorMessage(error, t('common.error')))
      }
    }
  } finally {
    uploading.value = false
  }
}

async function move(index: number, delta: number) {
  const next = [...images.value]
  const [item] = next.splice(index, 1)
  if (!item) return
  next.splice(index + delta, 0, item)
  try {
    const detail = await landlordApi.reorderImages(props.listingId, next.map(i => i.id))
    images.value = detail.images
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}

async function remove(image: ListingImage) {
  if (!window.confirm(t('console.confirmDeleteImage'))) return
  try {
    await landlordApi.deleteImage(props.listingId, image.id)
    images.value = images.value.filter(i => i.id !== image.id)
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}
</script>

<template>
  <section class="c-card">
    <h2>{{ t('console.images') }} <span class="c-hint">{{ images.length }} / {{ MAX_IMAGES }}</span></h2>
    <p class="c-hint">{{ t('console.imageHint') }}</p>
    <ul class="gallery">
      <li v-for="(image, index) in images" :key="image.id" class="gallery__item">
        <img :src="image.url" :alt="t('console.imageAlt', { n: index + 1 })" loading="lazy" />
        <span v-if="index === 0" class="c-badge gallery__cover" data-tone="good">{{ t('console.cover') }}</span>
        <div class="gallery__actions">
          <button type="button" class="c-btn c-btn--sm" :disabled="index === 0" :aria-label="t('console.moveLeft')" @click="move(index, -1)"><ArrowLeft :size="14" aria-hidden="true" /></button>
          <button type="button" class="c-btn c-btn--sm" :disabled="index === images.length - 1" :aria-label="t('console.moveRight')" @click="move(index, 1)"><ArrowRight :size="14" aria-hidden="true" /></button>
          <button type="button" class="c-btn c-btn--sm c-btn--danger" :aria-label="t('console.delete')" @click="remove(image)"><Trash2 :size="14" aria-hidden="true" /></button>
        </div>
      </li>
      <li v-if="images.length < MAX_IMAGES">
        <button type="button" class="gallery__add" :disabled="uploading" @click="input?.click()">
          <ImagePlus :size="26" aria-hidden="true" />{{ uploading ? t('console.uploading') : t('console.addImages') }}
        </button>
        <input ref="input" type="file" :accept="ACCEPT" multiple hidden @change="onFiles" />
      </li>
    </ul>
  </section>
</template>

<style scoped>
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-top: 10px; }
.gallery__item { position: relative; overflow: hidden; border: 1.5px solid var(--rule-strong); border-radius: 10px; background: var(--paper-muted); }
.gallery__item img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; }
.gallery__cover { position: absolute; left: 6px; top: 6px; }
.gallery__actions { display: flex; justify-content: flex-end; gap: 4px; padding: 6px; background: var(--paper-raised); }
.gallery__add { display: grid; place-items: center; gap: 6px; width: 100%; aspect-ratio: 4 / 3; border: 1.5px dashed var(--rule-strong); border-radius: 10px; color: var(--ink-secondary); font-weight: 800; cursor: pointer; }
.gallery__add:disabled { cursor: progress; opacity: .6; }
</style>
