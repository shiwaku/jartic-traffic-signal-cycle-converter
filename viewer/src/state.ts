import { createStore, type Store } from './lib/store'
import { LAYERS } from './map/layers/registry'
import { readUrlState } from './urlState'
import type { Basemap } from './map/basemap'
import type { Theme } from './theme'

const THEME_KEY = 'signal-cycle-theme'

export interface LayerState {
  visible: boolean
  opacity: number
}

/** クリックで選択された地物。ポップアップとハイライトの両方がこれから描かれる。 */
export interface Selection {
  layerKey: string
  properties: Record<string, unknown>
  geometry: GeoJSON.Geometry
  lngLat: { lng: number; lat: number }
}

export interface AppState {
  hour: number
  playing: boolean
  theme: Theme
  basemap: Basemap
  /** レイヤーキー → 表示状態。レイヤー定義（不変）とは分けて持つ。 */
  layers: Record<string, LayerState>
  selection: Selection | null
}

export type AppStore = Store<AppState>

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function savedTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY)
  return saved === 'light' || saved === 'dark' ? saved : systemTheme()
}

function initialLayers(): Record<string, LayerState> {
  return Object.fromEntries(
    LAYERS.map((m) => [m.def.key, { visible: m.def.defaultVisible, opacity: m.def.defaultOpacity }]),
  )
}

export function createAppStore(): AppStore {
  const defaults = initialLayers()
  // URL に載っていればそれを優先する（共有されたリンクを開いた場合）。
  const store = createStore<AppState>({
    hour: 0,
    playing: false,
    theme: savedTheme(),
    basemap: 'pale',
    layers: defaults,
    selection: null,
    ...readUrlState(defaults),
  })

  // テーマだけは次回の訪問にも引き継ぐ。
  store.subscribe((s, prev) => {
    if (s.theme !== prev.theme) localStorage.setItem(THEME_KEY, s.theme)
  })

  return store
}

// ---- 更新ヘルパー ----

/** 時間帯は 0〜23 で巡回させる（再生が23時から0時へ戻れるように）。 */
export function setHour(store: AppStore, hour: number): void {
  store.set({ hour: ((hour % 24) + 24) % 24 })
}

/** layers は丸ごと差し替える。参照が変わるので購読側は 1 回の比較で変化に気づける。 */
export function setLayerState(store: AppStore, key: string, patch: Partial<LayerState>): void {
  const layers = store.get().layers
  const next = { ...layers[key], ...patch }
  if (layers[key].visible === next.visible && layers[key].opacity === next.opacity) return
  store.set({ layers: { ...layers, [key]: next } })
}
