<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'
import { useDockSuppression } from '@/composables/useDockSuppression'

defineProps<{ title: string; wide?: boolean }>()
const open = defineModel<boolean>({ required: true })
const { t } = useI18n()
const dialog = ref<HTMLDialogElement | null>(null)

useDockSuppression(() => open.value)
watch(open, (value) => {
  if (value && !dialog.value?.open) dialog.value?.showModal()
  if (!value && dialog.value?.open) dialog.value.close()
}, { flush: 'post' })
// 以打开状态挂载（父组件 v-if 按需渲染）时也要弹出
onMounted(() => {
  if (open.value && !dialog.value?.open) dialog.value?.showModal()
})
</script>

<template>
  <dialog ref="dialog" class="c-dialog" :class="{ 'c-dialog--wide': wide }" @close="open = false">
    <header class="c-dialog__head">
      <h2>{{ title }}</h2>
      <button type="button" class="c-dialog__close" :aria-label="t('common.close')" @click="open = false"><X :size="20" aria-hidden="true" /></button>
    </header>
    <div v-if="open" class="c-dialog__body"><slot /></div>
  </dialog>
</template>

<style scoped>
.c-dialog { width: min(560px, calc(100vw - 24px)); max-height: calc(100dvh - 32px); margin: auto; padding: 0; overflow: auto; border: 2px solid var(--rule-strong); border-radius: 14px; background: var(--paper-raised); color: var(--ink); box-shadow: 5px 5px 0 var(--shadow-hard); }
.c-dialog--wide { width: min(820px, calc(100vw - 24px)); }
.c-dialog::backdrop { background: rgb(0 0 0 / .45); }
.c-dialog__head { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--rule); background: var(--paper-raised); }
.c-dialog__head h2 { font-size: 19px; font-weight: 900; }
.c-dialog__close { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 8px; }
.c-dialog__close:hover { background: var(--paper-muted); }
.c-dialog__body { display: grid; gap: 16px; padding: 18px 20px 20px; }
</style>
