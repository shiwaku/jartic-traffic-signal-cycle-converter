import type maplibregl from 'maplibre-gl'
import type { AppStore } from '../state'

const SRC = 'click-highlight'
export const HIGHLIGHT_BOTTOM_ID = 'click-highlight-fill'
const LINE = 'click-highlight-line'
const CIRCLE = 'click-highlight-circle'
const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

export interface Highlight {
  /** ハイライト層を（無ければ）作る。データ層はこれより背面に入る。 */
  ensure(): void
}

/** 選択された地物を黄色で強調する。選択状態は state が持ち、ここはそれを描くだけ。 */
export function createHighlight(map: maplibregl.Map, store: AppStore): Highlight {
  function ensure(): void {
    if (!map.getSource(SRC)) map.addSource(SRC, { type: 'geojson', data: EMPTY })
    if (!map.getLayer(HIGHLIGHT_BOTTOM_ID)) {
      map.addLayer({
        id: HIGHLIGHT_BOTTOM_ID,
        type: 'fill',
        source: SRC,
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: { 'fill-color': 'rgba(255,230,0,0.4)' },
      })
    }
    if (!map.getLayer(LINE)) {
      map.addLayer({
        id: LINE,
        type: 'line',
        source: SRC,
        filter: ['!=', ['geometry-type'], 'Point'],
        paint: { 'line-color': 'rgba(255,200,0,1)', 'line-width': 3 },
      })
    }
    if (!map.getLayer(CIRCLE)) {
      // 信号サイクルは点。選択位置に黄色いリングを重ねる。
      map.addLayer({
        id: CIRCLE,
        type: 'circle',
        source: SRC,
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
          'circle-radius': 9,
          'circle-color': 'rgba(0,0,0,0)',
          'circle-stroke-color': 'rgba(255,220,0,1)',
          'circle-stroke-width': 3,
        },
      })
    }
    render()
  }

  function render(): void {
    const src = map.getSource(SRC) as maplibregl.GeoJSONSource | undefined
    if (!src) return
    const sel = store.get().selection
    src.setData(
      sel
        ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: sel.geometry, properties: {} }] }
        : EMPTY,
    )
  }

  store.subscribe((s, prev) => {
    if (s.selection !== prev.selection) render()
  })

  return { ensure }
}
