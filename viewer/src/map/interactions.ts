import type maplibregl from 'maplibre-gl'
import { activePickIds } from './dataLayers'
import { layerByPickId } from './layers/registry'
import type { AppStore } from '../state'

/** クリックで選択、ホバーでカーソル変更。選択の結果はポップアップとハイライトが描く。 */
export function createInteractions(map: maplibregl.Map, store: AppStore): void {
  // ホバーカーソル（マウス環境のみ）
  if (window.matchMedia('(hover: hover)').matches) {
    map.on('mousemove', (e) => {
      const ids = activePickIds(map, store.get())
      const hit = ids.length > 0 && map.queryRenderedFeatures(e.point, { layers: ids }).length > 0
      map.getCanvas().style.cursor = hit ? 'pointer' : ''
    })
  }

  map.on('click', (e) => {
    const ids = activePickIds(map, store.get())
    const feats = ids.length ? map.queryRenderedFeatures(e.point, { layers: ids }) : []
    if (!feats.length) {
      // 何もない場所のクリック: 選択解除（ポップアップは closeOnClick が閉じる）
      store.set({ selection: null })
      return
    }
    const f = feats[0]
    const mod = layerByPickId(f.layer.id)
    if (!mod) return
    store.set({
      selection: {
        layerKey: mod.def.key,
        properties: f.properties as Record<string, unknown>,
        geometry: f.geometry,
        lngLat: { lng: e.lngLat.lng, lat: e.lngLat.lat },
      },
    })
  })
}
