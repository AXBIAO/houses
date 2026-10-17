<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { landlordApi } from '@/features/console/api'
import { errorMessage } from '@/features/console/errors'
import type { Block } from '@/features/console/types'
import { showToast } from '@/composables/useToast'

const props = defineProps<{ listingId: number }>()
const blocks = defineModel<Block[]>({ required: true })
const { t } = useI18n()
const form = reactive({ start: '', end: '', note: '' })
const saving = ref(false)
const errorText = ref('')
const today = new Date().toISOString().slice(0, 10)

async function add() {
  errorText.value = ''
  if (!form.start || !form.end || form.end <= form.start) {
    errorText.value = t('console.blockInvalid')
    return
  }
  saving.value = true
  try {
    const block = await landlordApi.addBlock(props.listingId, { ...form, note: form.note.trim() })
    blocks.value = [...blocks.value, block].sort((a, b) => a.startDate.localeCompare(b.startDate))
    Object.assign(form, { start: '', end: '', note: '' })
  } catch (error) {
    errorText.value = errorMessage(error, t('common.error'))
  } finally {
    saving.value = false
  }
}

async function remove(block: Block) {
  try {
    await landlordApi.deleteBlock(props.listingId, block.id)
    blocks.value = blocks.value.filter(b => b.id !== block.id)
  } catch (error) {
    showToast(errorMessage(error, t('common.error')))
  }
}
</script>

<template>
  <section class="c-card">
    <h2>{{ t('console.blocks') }}</h2>
    <p class="c-hint">{{ t('console.blockHint') }}</p>
    <ul v-if="blocks.length" class="blocks">
      <li v-for="b in blocks" :key="b.id">
        <span>{{ t('detail.bookedRange', { start: b.startDate, end: b.endDate }) }}</span>
        <span class="c-badge" :data-tone="b.kind === 'block' ? 'muted' : 'warn'">{{ t(`console.blockKind.${b.kind}`) }}</span>
        <span v-if="b.note" class="c-hint">{{ b.note }}</span>
        <button v-if="b.kind === 'block'" type="button" class="c-btn c-btn--sm c-btn--danger" @click="remove(b)">{{ t('console.delete') }}</button>
      </li>
    </ul>
    <form class="blocks__form" @submit.prevent="add">
      <label class="c-field">{{ t('console.blockStart') }}<input v-model="form.start" class="c-input" type="date" :min="today" required /></label>
      <label class="c-field">{{ t('console.blockEnd') }}<input v-model="form.end" class="c-input" type="date" :min="form.start || today" required /></label>
      <label class="c-field">{{ t('console.blockNote') }}<input v-model="form.note" class="c-input" maxlength="100" /></label>
      <button type="submit" class="c-btn" :disabled="saving">{{ t('console.addBlock') }}</button>
    </form>
    <p v-if="errorText" class="c-error" role="alert">{{ errorText }}</p>
  </section>
</template>

<style scoped>
.blocks { display: grid; gap: 8px; margin: 10px 0; }
.blocks li { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 8px; }
.blocks li .c-btn { margin-left: auto; }
.blocks__form { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); align-items: end; gap: 10px; margin-top: 10px; }
</style>
