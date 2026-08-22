import maplibregl from 'maplibre-gl'
import { layerByKey } from './layers/registry'
import type { AppStore } from '../state'

/**
 * 選択された地物のポップアップ。開閉は state.selection に従う。
 * ×ボタンや地図クリックで閉じられたときは、逆に選択を解除して state に返す。
 */
export function createPopup(map: maplibregl.Map, store: AppStore): void {
  let popup: maplibregl.Popup | null = null

  function close(): void {
    if (!popup) return
    // close ハンドラの誤発火を防ぐため、参照を外してから remove する
    const old = popup
    popup = null
    old.remove()
  }

  function render(): void {
    close()
    const sel = store.get().selection
    if (!sel) return
    const mod = layerByKey(sel.layerKey)
    if (!mod) return

    const { hour, theme } = store.get()
    const p = new maplibregl.Popup({ closeButton: true, maxWidth: '320px' })
      .setLngLat(sel.lngLat)
      .setHTML(mod.popupHtml(sel.properties, sel.lngLat.lng, sel.lngLat.lat, { hour, theme }))
      .addTo(map)
    p.on('close', () => {
      if (popup !== p) return
      popup = null
      store.set({ selection: null })
    })
    popup = p
  }

  store.subscribe((s, prev) => {
    if (s.selection !== prev.selection) render()
  })
}
