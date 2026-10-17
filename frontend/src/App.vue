<script setup lang="ts">
// Modified for Houses (based on AIGCNEWS, AGPL-3.0)
import { RouterView } from 'vue-router'
import AppToast from '@/components/AppToast.vue'
import RouteProgress from '@/components/RouteProgress.vue'
import { useLocaleTransition } from './composables/useLocaleTransition'

const { isLocaleTransitioning } = useLocaleTransition()
</script>

<template>
  <div class="app-backdrop" aria-hidden="true"></div>
  <div class="app-noise" aria-hidden="true"></div>

  <RouterView />
  <RouteProgress />
  <AppToast />

  <Transition name="locale-refresh">
    <div v-if="isLocaleTransitioning" class="locale-refresh" aria-hidden="true">
      <span class="locale-refresh__sweep" />
    </div>
  </Transition>
</template>
