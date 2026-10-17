<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'

const MAX_TAGS = 10
const MAX_LENGTH = 12
const SUGGESTIONS = ['近地铁', '拎包入住', '押一付一', '电梯房', '独卫', '可养宠物', '可做饭', '阳台', '新装修', '智能门锁', '可停车', '月付'] as const

const tags = defineModel<string[]>({ required: true })
const { t } = useI18n()
const draft = ref('')

function add(raw: string) {
  const tag = raw.trim().slice(0, MAX_LENGTH)
  if (!tag || tags.value.includes(tag) || tags.value.length >= MAX_TAGS) return
  tags.value = [...tags.value, tag]
}
function commit() {
  add(draft.value)
  draft.value = ''
}
function remove(tag: string) {
  tags.value = tags.value.filter(x => x !== tag)
}
</script>

<template>
  <div class="tags">
    <ul class="tags__list">
      <li v-for="tag in tags" :key="tag" class="c-badge">
        {{ tag }}<button type="button" :aria-label="t('console.removeTag', { tag })" @click="remove(tag)"><X :size="12" aria-hidden="true" /></button>
      </li>
      <li class="tags__input">
        <input
          v-model="draft" class="c-input" :maxlength="MAX_LENGTH" :placeholder="t('console.tagPlaceholder')"
          :disabled="tags.length >= MAX_TAGS" :aria-label="t('filters.tags')" @keydown.enter.prevent="commit" @blur="commit"
        />
      </li>
    </ul>
    <div class="tags__suggest">
      <button v-for="s in SUGGESTIONS.filter(x => !tags.includes(x))" :key="s" type="button" class="c-btn c-btn--sm" @click="add(s)">+ {{ s }}</button>
    </div>
  </div>
</template>

<style scoped>
.tags { display: grid; gap: 8px; }
.tags__list { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.tags__list .c-badge { gap: 4px; height: 28px; }
.tags__list button { display: grid; place-items: center; }
.tags__input { flex: 1; min-width: 160px; }
.tags__suggest { display: flex; flex-wrap: wrap; gap: 6px; }
</style>
