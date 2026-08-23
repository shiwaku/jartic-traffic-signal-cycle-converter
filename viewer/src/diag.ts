import type maplibregl from 'maplibre-gl'
import { isMobile } from './lib/env'
import { LAYERS } from './map/layers/registry'
import type { AppStore } from './state'

export const DEBUG = new URLSearchParams(location.search).has('debug')

/** ?debug で画面に出す診断HUD。実機での原因切り分け用。 */
export function createDiag(map: maplibregl.Map, store: AppStore): void {
  const log: string[] = []
  let ctxLostCount = 0
  let hud: HTMLElement | null = null

  function say(msg: string): void {
    const line = `${new Date().toISOString().slice(11, 19)} ${msg}`
    log.push(line)
    if (log.length > 8) log.shift()
    console.log('[diag]', line)
    render()
  }

  function render(): void {
    if (!DEBUG || !hud) return
    const state = store.get()
    const rows = LAYERS.filter((m) => state.layers[m.def.key].visible)
      .map((m) => {
        let n = 0
        try {
          n = map.getLayer(m.pickLayerId) ? map.queryRenderedFeatures({ layers: [m.pickLayerId] }).length : -1
        } catch {
          n = -2
        }
        return `${m.def.key}: ${n}`
      })
      .join('  ')
    hud.innerHTML =
      `<b>build ${__BUILD_TIME__}</b><br>` +
      `zoom ${map.getZoom().toFixed(1)} · hour ${state.hour} · mobile ${isMobile} · ctxLost ${ctxLostCount}<br>` +
      `<u>rendered features / layer</u><br>${rows || '(none)'}<br>` +
      `<u>log</u><br>${log.join('<br>')}`
  }

  if (DEBUG) {
    hud = document.createElement('div')
    hud.id = 'diag-hud'
    document.body.append(hud)
    render()
    map.on('render', () => {
      if (map.areTilesLoaded()) render()
    })
  }

  // WebGL コンテキスト消失。preventDefault しないと自動復帰イベントが発火しない。
  // 貼り直し自体は dataLayers が webglcontextrestored で行う。
  const canvas = map.getCanvas()
  canvas.addEventListener(
    'webglcontextlost',
    (e) => {
      e.preventDefault()
      ctxLostCount++
      say('WebGL context lost')
    },
    false,
  )
  canvas.addEventListener('webglcontextrestored', () => say('WebGL context restored → relayering'), false)

  map.on('error', (e) => {
    const msg = (e && (e as unknown as { error?: Error }).error?.message) || 'map error'
    say(`error: ${msg}`)
  })
}
