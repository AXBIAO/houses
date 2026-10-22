<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadAMap, type AMapNamespace } from './amapLoader'
import type { MapBounds, MapMarker } from './LeafletMap.vue'

/** 高德 JS API 2.0 底图，props / 事件 / flyTo 与 LeafletMap 一致。注意高德的坐标顺序是 [lng, lat]（GCJ-02）。 */
const props = withDefaults(defineProps<{
  amapKey: string
  center: [number, number]
  zoom?: number
  markers: readonly MapMarker[]
  activeId?: number | null
  interactive?: boolean
}>(), { zoom: 13, activeId: null, interactive: true })

const emit = defineEmits<{ bounds: [bounds: MapBounds]; select: [id: number]; pick: [lat: number, lng: number]; failed: [] }>()

const BOUNDS_DEBOUNCE_MS = 300
const container = ref<HTMLDivElement | null>(null)
let AMap: AMapNamespace | null = null
let map: any = null
let overlays: any[] = []
let boundsTimer: number | undefined
let disposed = false

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c)
}

function renderMarkers() {
  if (!map || !AMap) return
  map.remove(overlays)
  overlays = props.markers.map((m) => {
    const active = m.id === props.activeId
    const marker = new AMap!.Marker({
      position: [m.lng, m.lat],
      content: `<span class="price-pin${active ? ' is-active' : ''}" data-kind="${escapeHtml(m.kind ?? '')}">${escapeHtml(m.label)}</span>`,
      anchor: 'bottom-center',
      zIndex: active ? 200 : 100,
      title: m.label,
    })
    marker.on('click', () => emit('select', m.id))
    return marker
  })
  map.add(overlays)
}

function emitBounds() {
  if (!map) return
  const b = map.getBounds()
  const sw = b.getSouthWest()
  const ne = b.getNorthEast()
  emit('bounds', { minLng: sw.getLng(), minLat: sw.getLat(), maxLng: ne.getLng(), maxLat: ne.getLat() })
}

function scheduleBounds() {
  window.clearTimeout(boundsTimer)
  boundsTimer = window.setTimeout(emitBounds, BOUNDS_DEBOUNCE_MS)
}

onMounted(async () => {
  try {
    AMap = await loadAMap(props.amapKey)
  } catch {
    if (!disposed) emit('failed')
    return
  }
  if (disposed || !container.value) return
  try {
    createMap(AMap, container.value)
  } catch {
    // 脚本加载成功但初始化失败（如被 CSP 拦截插件）：交给外层退回 OpenStreetMap
    map?.destroy()
    map = null
    emit('failed')
  }
})

function createMap(AMap: AMapNamespace, el: HTMLDivElement) {
  map = new AMap.Map(el, {
    center: [props.center[1], props.center[0]],
    zoom: props.zoom,
    dragEnable: props.interactive,
    zoomEnable: props.interactive,
    doubleClickZoom: props.interactive,
    keyboardEnable: props.interactive,
    viewMode: '2D',
  })
  if (props.interactive) {
    map.addControl(new AMap.Scale())
    map.addControl(new AMap.ToolBar({ position: 'RB' }))
  }
  map.on('moveend', scheduleBounds)
  map.on('zoomend', scheduleBounds)
  map.on('click', (e: any) => emit('pick', e.lnglat.getLat(), e.lnglat.getLng()))
  map.on('complete', emitBounds)
  renderMarkers()
}

watch(() => [props.markers, props.activeId], renderMarkers)
watch(() => props.center, center => map?.setCenter([center[1], center[0]]))

onBeforeUnmount(() => {
  disposed = true
  window.clearTimeout(boundsTimer)
  map?.destroy()
  map = null
})

defineExpose({
  flyTo: (lat: number, lng: number, zoom?: number) => map?.setZoomAndCenter(zoom ?? map.getZoom(), [lng, lat]),
})
</script>

<template>
  <div ref="container" class="amap-host" />
</template>

<style scoped>
.amap-host { width: 100%; height: 100%; min-height: 240px; border-radius: inherit; overflow: hidden; z-index: 0; }
:deep(.price-pin) {
  display: inline-block; padding: 3px 9px; white-space: nowrap;
  border: 1.5px solid #151512; border-radius: 999px; background: #fffefa; color: #151512;
  font: 800 12px/1.4 system-ui, sans-serif; box-shadow: 2px 2px 0 #151512; cursor: pointer;
}
:deep(.price-pin[data-kind='short']) { background: #bfe3ff; }
:deep(.price-pin[data-kind='shared']) { background: #ffd9b8; }
:deep(.price-pin[data-kind='mixed']) { background: #f1e6ff; }
:deep(.price-pin.is-active) { background: #d8f14b; transform: scale(1.15); transform-origin: bottom center; }
</style>
