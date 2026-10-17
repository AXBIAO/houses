<script setup lang="ts">
defineProps<{ count: number }>()
</script>

<template>
  <div class="skeleton-grid" aria-hidden="true">
    <div v-for="i in count" :key="i" class="skeleton-card">
      <div class="skeleton-card__cover" />
      <div class="skeleton-card__line skeleton-card__line--short" />
      <div class="skeleton-card__line" />
      <div class="skeleton-card__line skeleton-card__line--mid" />
    </div>
  </div>
</template>

<style scoped>
.skeleton-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 18px; }
.skeleton-card { display: grid; gap: 10px; padding-bottom: 16px; border: 1.5px solid var(--rule); border-radius: 14px; overflow: hidden; background: var(--paper-raised); }
.skeleton-card__cover { aspect-ratio: 16 / 10; background: var(--paper-muted); animation: pulse 1.4s ease-in-out infinite; }
.skeleton-card__line { height: 12px; margin: 0 14px; border-radius: 6px; background: var(--paper-muted); animation: pulse 1.4s ease-in-out infinite; }
.skeleton-card__line--short { width: 40%; height: 18px; }
.skeleton-card__line--mid { width: 60%; }
@keyframes pulse { 50% { opacity: .5; } }
@media (prefers-reduced-motion: reduce) { .skeleton-card__cover, .skeleton-card__line { animation: none; } }
</style>
