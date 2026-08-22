import { createDiag } from './diag'
import { createMap } from './map/createMap'
import { createDataLayers } from './map/dataLayers'
import { createHighlight } from './map/highlight'
import { createInteractions } from './map/interactions'
import { createPopup } from './map/popup'
import { registerServiceWorker } from './pwa'
import { createAppStore } from './state'
import { syncUrlState } from './urlState'
import { createBasemapSwitch } from './ui/basemapSwitch'
import { createDatasetInfo } from './ui/datasetInfo'
import { createTimebar } from './ui/timebar'
import { createLayerPanel } from './ui/layerPanel'
import { createPanel } from './ui/panel'
import { createThemeToggle } from './ui/themeToggle'
import './style.css'

// 状態は store に1本化してある。UI も地図もこれを購読するだけで、互いを直接書き換えない。
const store = createAppStore()
const map = createMap('map', store.get())

// 地図側
const highlight = createHighlight(map, store)
createDataLayers(map, store, highlight)
createInteractions(map, store)
createPopup(map, store)
createBasemapSwitch(map, store)

// UI 側
createThemeToggle(store)
createPanel()
createTimebar(store)
createLayerPanel(store)
createDatasetInfo()

syncUrlState(store)
createDiag(map, store)
registerServiceWorker()

const buildEl = document.getElementById('build-ver')
if (buildEl) buildEl.textContent = `build: ${__BUILD_TIME__}`

// デバッグ/外部連携用にマップとストアを公開
;(window as unknown as { __map: typeof map; __store: typeof store }).__map = map
;(window as unknown as { __map: typeof map; __store: typeof store }).__store = store
