import type maplibregl from 'maplibre-gl'
import { getBasemapStyle } from './basemap'
import type { Highlight } from './highlight'
import { HIGHLIGHT_BOTTOM_ID } from './highlight'
import { LAYERS } from './layers/registry'
import type { LayerModule, PaintContext } from './layers/types'
import type { AppState, AppStore } from '../state'

const PMTILES_BASE = import.meta.env.VITE_PMTILES_BASE ?? '/pmtiles'

/** 有効なレイヤーの ID のうち、地図に載っているもの（クリック判定に使う）。 */
export function activePickIds(map: maplibregl.Map, state: AppState): string[] {
  return LAYERS.filter((m) => state.layers[m.def.key].visible)
    .map((m) => m.pickLayerId)
    .filter((id) => map.getLayer(id))
}

export function createDataLayers(map: maplibregl.Map, store: AppStore, highlight: Highlight): void {
  const ctxFor = (mod: LayerModule): PaintContext => {
    const s = store.get()
    return { hour: s.hour, theme: s.theme, opacity: s.layers[mod.def.key].opacity }
  }

  // canonical z順: LAYERS 配列の後ろほど地図で最前面。
  // mod の直上に来るべき既存レイヤーを beforeId に指定して正規順で挿入する。
  // クリックハイライト層は常に全データ層より前面に保つ。
  function beforeIdFor(mod: LayerModule): string | undefined {
    const i = LAYERS.indexOf(mod)
    for (let j = i + 1; j < LAYERS.length; j++) {
      for (const id of LAYERS[j].layerIds) {
        if (map.getLayer(id)) return id
      }
    }
    return map.getLayer(HIGHLIGHT_BOTTOM_ID) ? HIGHLIGHT_BOTTOM_ID : undefined
  }

  function ensureLayer(mod: LayerModule): void {
    if (!map.getSource(mod.def.key)) {
      map.addSource(mod.def.key, {
        type: 'vector',
        url: `pmtiles://${PMTILES_BASE}/${mod.def.file}.pmtiles`,
        attribution: mod.def.attribution,
      })
    }
    const before = beforeIdFor(mod)
    for (const spec of mod.specs(ctxFor(mod))) {
      if (map.getLayer(spec.id)) continue
      map.addLayer(spec, before)
    }
  }

  function removeLayer(mod: LayerModule): void {
    for (const id of mod.layerIds) {
      if (map.getLayer(id)) map.removeLayer(id)
    }
    if (map.getSource(mod.def.key)) map.removeSource(mod.def.key)
  }

  /** 有効なレイヤーのみを（正規 z順で）地図に載せる。無効なものはソースごと持たない＝軽量。 */
  function sync(): void {
    // 先にハイライト層を作っておくと、データ層は beforeIdFor 経由で常にその下に入る
    highlight.ensure()
    const state = store.get()
    for (const mod of LAYERS) {
      if (state.layers[mod.def.key].visible) ensureLayer(mod)
      else removeLayer(mod)
    }
  }

  /**
   * 現在の時間帯・テーマ・不透明度を paint に反映する。
   * 1交差点1フィーチャに24時間分の値を持たせているので、時間帯の切替は「どの属性を見るか」を
   * paint 式の中で変えるだけで済む。setFilter と違いタイルの再評価が走らない。
   */
  function applyPaint(): void {
    const state = store.get()
    for (const mod of LAYERS) {
      if (!state.layers[mod.def.key].visible) continue
      for (const u of mod.paintUpdates(ctxFor(mod))) {
        if (map.getLayer(u.id)) map.setPaintProperty(u.id, u.prop, u.value)
      }
    }
  }

  // 背景スタイルを差し替える。ラスタ（写真）↔ベクタ（淡色）の切替では diff 適用が
  // 効かず背景が入れ替わらないため diff:false で完全に再構築する。
  // setStyle 直後は isStyleLoaded() が旧スタイルで true を返して競合するため、
  // 新スタイルの描画が落ち着く idle を待ってからデータ層を再追加する。
  function reloadStyle(): void {
    const s = store.get()
    map.setStyle(getBasemapStyle(s.basemap, s.theme), { diff: false })
    map.once('idle', sync)
  }

  store.subscribe((s, prev) => {
    if (s.theme !== prev.theme || s.basemap !== prev.basemap) {
      reloadStyle()
      return
    }
    if (s.layers !== prev.layers) {
      sync()
      applyPaint()
      return
    }
    if (s.hour !== prev.hour) applyPaint()
  })

  map.on('load', sync)

  // WebGL コンテキスト消失からの復帰。iOS Safari 等ではメモリ逼迫時に GL コンテキストが
  // 失われ、データ層がまるごと消えて戻らないことがある。復帰時に貼り直して自動回復する。
  map.getCanvas().addEventListener(
    'webglcontextrestored',
    () => {
      if (map.isStyleLoaded()) sync()
      else map.once('idle', sync)
    },
    false,
  )
}
