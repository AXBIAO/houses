<script setup lang="ts">
import { computed, ref } from 'vue'
import AMapMap from './AMapMap.vue'
import LeafletMap, { type MapBounds, type MapMarker } from './LeafletMap.vue'
import { useSiteInfo } from '@/composables/useSiteInfo'

/** 配置了高德 Key 用高德地图；没配或加载失败（被拦截、Key 失效）时退回 OpenStreetMap。 */
withDefaults(defineProps<{
  center: [number, number]
  zoom?: number
  markers: readonly MapMarker[]
  activeId?: number | null
  interactive?: boolean
}>(), { zoom: 13, activeId: null, interactive: true })
const emit = defineEmits<{ bounds: [bounds: MapBounds]; select: [id: number]; pick: [lat: number, lng: number] }>()

const site = useSiteInfo()
const amapFailed = ref(false)
const provider = computed(() => {
  if (!site.ready) return null
  return site.amapKey && !amapFailed.value ? 'amap' : 'osm'
})
const inner = ref<{ flyTo: (lat: number, lng: number, zoom?: number) => void } | null>(null)

defineExpose({
  flyTo: (lat: number, lng: number, zoom?: number) => inner.value?.flyTo(lat, lng, zoom),
})
</script>

<template>
  <AMapMap
    v-if="provider === 'amap'" ref="inner" :amap-key="site.amapKey"
    :center="center" :zoom="zoom" :markers="markers" :active-id="activeId" :interactive="interactive"
    @bounds="emit('bounds', $event)" @select="emit('select', $event)" @pick="(lat, lng) => emit('pick', lat, lng)"
    @failed="amapFailed = true"
  />
  <LeafletMap
    v-else-if="provider === 'osm'" ref="inner"
    :center="center" :zoom="zoom" :markers="markers" :active-id="activeId" :interactive="interactive"
    @bounds="emit('bounds', $event)" @select="emit('select', $event)" @pick="(lat, lng) => emit('pick', lat, lng)"
  />
  <div v-else class="house-map-placeholder" aria-hidden="true" />
</template>

<style scoped>
.house-map-placeholder { width: 100%; height: 100%; min-height: 240px; border-radius: inherit; background: #eceae2; }
</style>
