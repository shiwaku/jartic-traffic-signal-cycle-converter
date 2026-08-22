import { LAYERS } from './map/layers/registry'
import type { AppState, AppStore, LayerState } from './state'

/**
 * 表示状態を URL のクエリに載せる。
 *
 *   ?h=7&l=signal&t=dark&b=photo#12/35.17/136.90
 *
 * 地図の位置（#ズーム/緯度/経度）は MapLibre の hash が持つので、こちらは触らない。
 * 「朝7時の名古屋」のような画面をそのまま共有できるようにするための機能。
 */

const KEYS = { hour: 'h', layers: 'l', theme: 't', basemap: 'b' } as const

/** URL から読み取れた分だけを返す。不正な値は無視して既定にまかせる。 */
export function readUrlState(defaults: Record<string, LayerState>): Partial<AppState> {
  const q = new URLSearchParams(location.search)
  const out: Partial<AppState> = {}

  const hour = Number(q.get(KEYS.hour))
  if (q.has(KEYS.hour) && Number.isInteger(hour) && hour >= 0 && hour <= 23) out.hour = hour

  const theme = q.get(KEYS.theme)
  if (theme === 'light' || theme === 'dark') out.theme = theme

  const basemap = q.get(KEYS.basemap)
  if (basemap === 'pale' || basemap === 'photo') out.basemap = basemap

  const raw = q.get(KEYS.layers)
  if (raw !== null) {
    // 空文字は「全部OFF」。未知のキーは無視する。
    const on = new Set(raw.split(',').filter(Boolean))
    out.layers = Object.fromEntries(
      LAYERS.map((m) => [m.def.key, { ...defaults[m.def.key], visible: on.has(m.def.key) }]),
    )
  }

  return out
}

/** 状態が変わるたびに URL を書き換える。再生中に履歴が溜まらないよう replaceState を使う。 */
export function syncUrlState(store: AppStore): void {
  function write(): void {
    const s = store.get()
    const q = new URLSearchParams(location.search)
    q.set(KEYS.hour, String(s.hour))
    q.set(KEYS.theme, s.theme)
    q.set(KEYS.basemap, s.basemap)
    q.set(
      KEYS.layers,
      LAYERS.filter((m) => s.layers[m.def.key].visible)
        .map((m) => m.def.key)
        .join(','),
    )
    history.replaceState(null, '', `${location.pathname}?${q}${location.hash}`)
  }

  store.subscribe((s, prev) => {
    if (s.hour !== prev.hour || s.theme !== prev.theme || s.basemap !== prev.basemap || s.layers !== prev.layers) {
      write()
    }
  })

  write()
}
