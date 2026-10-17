<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export interface MapMarker {
  id: number
  lat: number
  lng: number
  label: string
  kind?: string
}

export interface MapBounds {
  minLng: number
  minLat: number
  maxLng: number
  maxLat: number
}

/** 免 Key 的 OpenStreetMap 底图；OSM 使用条款要求保留署名。 */
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
const BOUNDS_DEBOUNCE_MS = 300

const props = withDefaults(defineProps<{
  center: [number, number]
  zoom?: number
  markers: readonly MapMarker[]
  activeId?: number | null
  interactive?: boolean
}>(), { zoom: 13, activeId: null, interactive: true })

const emit = defineEmits<{ bounds: [bounds: MapBounds]; select: [id: number]; pick: [lat: number, lng: number] }>()

const container = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let layer: L.LayerGroup | null = null
let boundsTimer: number | undefined

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c)
}

function renderMarkers() {
  if (!map || !layer) return
  layer.clearLayers()
  for (const m of props.markers) {
    const active = m.id === props.activeId
    const icon = L.divIcon({
      className: 'price-pin-host',
      html: `<span class="price-pin${active ? ' is-active' : ''}" data-kind="${escapeHtml(m.kind ?? '')}">${escapeHtml(m.label)}</span>`,
      iconSize: undefined,
      iconAnchor: [0, 0],
    })
    L.marker([m.lat, m.lng], { icon, zIndexOffset: active ? 1000 : 0, keyboard: true, title: m.label })
      .on('click', () => emit('select', m.id))
      .addTo(layer)
  }
}

function emitBounds() {
  if (!map) return
  const b = map.getBounds()
  emit('bounds', { minLng: b.getWest(), minLat: b.getSouth(), maxLng: b.getEast(), maxLat: b.getNorth() })
}

function scheduleBounds() {
  window.clearTimeout(boundsTimer)
  boundsTimer = window.setTimeout(emitBounds, BOUNDS_DEBOUNCE_MS)
}

onMounted(() => {
  if (!container.value) return
  map = L.map(container.value, {
    center: props.center,
    zoom: props.zoom,
    zoomControl: props.interactive,
    dragging: props.interactive,
    scrollWheelZoom: props.interactive,
    doubleClickZoom: props.interactive,
    touchZoom: props.interactive,
  })
  L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map)
  layer = L.layerGroup().addTo(map)
  map.on('moveend', scheduleBounds)
  map.on('click', (e: L.LeafletMouseEvent) => emit('pick', e.latlng.lat, e.latlng.lng))
  renderMarkers()
  emitBounds()
})

watch(() => [props.markers, props.activeId], renderMarkers)
watch(() => props.center, (center) => map?.setView(center, map.getZoom()))

onBeforeUnmount(() => {
  window.clearTimeout(boundsTimer)
  map?.remove()
  map = null
})

defineExpose({
  flyTo: (lat: number, lng: number, zoom?: number) => map?.flyTo([lat, lng], zoom ?? map.getZoom()),
})
</script>

<template>
  <div ref="container" class="leaflet-host" />
</template>

<style scoped>
.leaflet-host { width: 100%; height: 100%; min-height: 240px; border-radius: inherit; z-index: 0; }
:deep(.price-pin-host) { background: none; border: 0; }
:deep(.price-pin) {
  display: inline-block; transform: translate(-50%, -100%); padding: 3px 9px; white-space: nowrap;
  border: 1.5px solid #151512; border-radius: 999px; background: #fffefa; color: #151512;
  font: 800 12px/1.4 system-ui, sans-serif; box-shadow: 2px 2px 0 #151512; cursor: pointer;
}
:deep(.price-pin[data-kind='short']) { background: #bfe3ff; }
:deep(.price-pin[data-kind='shared']) { background: #ffd9b8; }
:deep(.price-pin[data-kind='mixed']) { background: #f1e6ff; }
:deep(.price-pin.is-active) { background: #d8f14b; transform: translate(-50%, -100%) scale(1.15); }
</style>
