import maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'

import { getBasemapStyle, type Basemap } from './basemap'
import {
  LAYERS,
  type LayerDef,
  hourFilter,
  hourFilteredLayerIds,
  layerIdsOf,
  layerSpecs,
  legendFor,
  opacityOf,
  opacityUpdates,
  pickLayerIdOf,
  popupHtml,
} from './layers'
import { applyThemeAttr, initialTheme, type Theme } from './theme'
import './style.css'

const PMTILES_BASE = import.meta.env.VITE_PMTILES_BASE ?? '/pmtiles'
const SITE_ATTRIBUTION =
  '（<a href="https://x.com/shi__works" target="_blank" rel="noopener">X</a> | <a href="https://github.com/shiwaku/jartic-traffic-signal-cycle-converter" target="_blank" rel="noopener">GitHub</a>）'

let theme: Theme = initialTheme()
let base: Basemap = 'pale'
let hour = 0
applyThemeAttr(theme)

const isMobile = window.matchMedia('(max-width: 640px)').matches
const DEBUG = new URLSearchParams(location.search).has('debug')

const protocol = new Protocol()
maplibregl.addProtocol('pmtiles', protocol.tile)

const map = new maplibregl.Map({
  container: 'map',
  style: getBasemapStyle(base, theme),
  center: [139.6226196, 35.4660694],
  zoom: 9,
  // 地図位置を URL の #ズーム/緯度/経度 に反映（共有・リロード時の位置維持）
  hash: true,
  attributionControl: false,
  // モバイルは GPU/メモリが限られるため保持タイル数を絞る（コンテキスト消失の予防）
  maxTileCacheSize: isMobile ? 24 : undefined,
  pixelRatio: isMobile ? Math.min(window.devicePixelRatio || 1, 2) : undefined,
})
map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), 'top-right')
map.addControl(new maplibregl.FullscreenControl(), 'top-right')
map.addControl(
  new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: false },
    fitBoundsOptions: { maxZoom: 18 },
    trackUserLocation: true,
    showUserLocation: true,
  }),
  'top-right',
)
map.addControl(new maplibregl.ScaleControl({ maxWidth: 200, unit: 'metric' }), 'bottom-left')
map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: SITE_ATTRIBUTION }))

const defOf = (key: string): LayerDef | undefined => LAYERS.find((d) => d.key === key)
/** クリック判定に使う、現在有効なレイヤー ID。 */
const activePickIds = (): string[] =>
  LAYERS.filter((d) => d.on)
    .map((d) => pickLayerIdOf(d))
    .filter((id) => map.getLayer(id))

// ---- クリックハイライト（選択地物を黄色で強調） ----
const HL_SRC = 'click-highlight'
const HL_FILL = 'click-highlight-fill'
const HL_LINE = 'click-highlight-line'
const HL_CIRCLE = 'click-highlight-circle'
const EMPTY_FC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

function ensureHighlightLayers(): void {
  if (!map.getSource(HL_SRC)) map.addSource(HL_SRC, { type: 'geojson', data: EMPTY_FC })
  if (!map.getLayer(HL_FILL)) {
    map.addLayer({
      id: HL_FILL,
      type: 'fill',
      source: HL_SRC,
      filter: ['==', ['geometry-type'], 'Polygon'],
      paint: { 'fill-color': 'rgba(255,230,0,0.4)' },
    })
  }
  if (!map.getLayer(HL_LINE)) {
    map.addLayer({
      id: HL_LINE,
      type: 'line',
      source: HL_SRC,
      filter: ['!=', ['geometry-type'], 'Point'],
      paint: { 'line-color': 'rgba(255,200,0,1)', 'line-width': 3 },
    })
  }
  if (!map.getLayer(HL_CIRCLE)) {
    // 信号サイクルは点。選択位置に黄色いリングを重ねる。
    map.addLayer({
      id: HL_CIRCLE,
      type: 'circle',
      source: HL_SRC,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 9,
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': 'rgba(255,220,0,1)',
        'circle-stroke-width': 3,
      },
    })
  }
}

function setHighlight(f: maplibregl.MapGeoJSONFeature | null): void {
  const src = map.getSource(HL_SRC) as maplibregl.GeoJSONSource | undefined
  if (!src) return
  src.setData(
    f ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: f.geometry, properties: {} }] } : EMPTY_FC,
  )
}

// ---- データレイヤーの追加・削除 ----

// canonical z順: LAYERS 配列の後ろほど地図で最前面。
// def の直上に来るべき既存レイヤーを beforeId に指定して正規順で挿入する。
// クリックハイライト層は常に全データ層より前面に保つ。
function beforeIdFor(def: LayerDef): string | undefined {
  const i = LAYERS.findIndex((d) => d.key === def.key)
  for (let j = i + 1; j < LAYERS.length; j++) {
    for (const id of layerIdsOf(LAYERS[j])) {
      if (map.getLayer(id)) return id
    }
  }
  return map.getLayer(HL_FILL) ? HL_FILL : undefined
}

function ensureLayer(def: LayerDef): void {
  if (!map.getSource(def.key)) {
    map.addSource(def.key, {
      type: 'vector',
      url: `pmtiles://${PMTILES_BASE}/${def.file}.pmtiles`,
      attribution: def.attribution,
    })
  }
  const before = beforeIdFor(def)
  for (const spec of layerSpecs(def)) {
    if (map.getLayer(spec.id)) continue
    map.addLayer(spec, before)
  }
  applyHourFilter()
}

function removeLayer(def: LayerDef): void {
  for (const id of layerIdsOf(def)) {
    if (map.getLayer(id)) map.removeLayer(id)
  }
  if (map.getSource(def.key)) map.removeSource(def.key)
}

/** 有効なレイヤーのみを（正規 z順で）地図に載せる。無効なものはソースごと持たない＝軽量。 */
function addDataLayers(): void {
  // 先にハイライト層を作っておくと、データ層は beforeIdFor 経由で常にその下に入る
  ensureHighlightLayers()
  for (const def of LAYERS) {
    if (def.on) ensureLayer(def)
    else removeLayer(def)
  }
}

// ---- 時間帯 ----

function applyHourFilter(): void {
  const filter = hourFilter(hour)
  for (const id of hourFilteredLayerIds()) {
    if (map.getLayer(id)) map.setFilter(id, filter)
  }
}

const hourSlider = document.getElementById('hour-slider') as HTMLInputElement
const hourLabel = document.getElementById('hour-label') as HTMLOutputElement

function setHour(next: number): void {
  hour = ((next % 24) + 24) % 24
  hourSlider.value = String(hour)
  hourLabel.textContent = `${hour}時`
  applyHourFilter()
}

hourSlider.addEventListener('input', () => setHour(Number(hourSlider.value)))

// 0→23時を巡回再生する。時間帯ごとの混み具合の移り変わりを見るための機能。
const playBtn = document.getElementById('play-btn') as HTMLButtonElement
let timer: number | null = null

function setPlaying(on: boolean): void {
  if (on && timer === null) {
    timer = window.setInterval(() => setHour(hour + 1), 900)
  } else if (!on && timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
  playBtn.textContent = timer === null ? '▶ 再生' : '❙❙ 停止'
  playBtn.setAttribute('aria-pressed', String(timer !== null))
}
playBtn.addEventListener('click', () => setPlaying(timer === null))

// ---- テーマ切替 ----
const themeBtn = document.getElementById('theme-btn') as HTMLButtonElement
const renderThemeBtn = (): void => {
  themeBtn.textContent = theme === 'dark' ? '☀️' : '🌙'
}
// 背景スタイルを差し替える。ラスタ（写真）↔ベクタ（淡色）の切替では diff 適用が
// 効かず背景が入れ替わらないため diff:false で完全に再構築する。
// setStyle 直後は isStyleLoaded() が旧スタイルで true を返して競合するため、
// 新スタイルの描画が落ち着く idle を待ってからデータ層を再追加する。
function reloadStyle(): void {
  map.setStyle(getBasemapStyle(base, theme), { diff: false })
  map.once('idle', () => addDataLayers())
}
themeBtn.addEventListener('click', () => {
  theme = theme === 'dark' ? 'light' : 'dark'
  applyThemeAttr(theme)
  renderThemeBtn()
  reloadStyle()
})

// ---- パネル開閉 ----
const panel = document.getElementById('panel') as HTMLElement
const collapseBtn = document.getElementById('collapse-btn') as HTMLButtonElement
const renderCollapseBtn = (): void => {
  collapseBtn.textContent = panel.classList.contains('collapsed') ? '▾' : '▴'
}
collapseBtn.addEventListener('click', () => {
  panel.classList.toggle('collapsed')
  renderCollapseBtn()
})

// ---- レイヤートグル（凡例を各レイヤー直下にインライン表示） ----
const layersDiv = document.getElementById('layers') as HTMLElement

function legendMarkup(def: LayerDef): string {
  return legendFor(def)
    .map(
      (it) =>
        `<span class="lg-row"><span class="lg-sw lg-${it.shape}" style="background:${it.color}"></span>${it.label}</span>`,
    )
    .join('')
}

function buildToggles(): void {
  for (const def of LAYERS) {
    const item = document.createElement('div')
    item.className = 'layer-item'
    item.dataset.key = def.key

    const label = document.createElement('label')
    label.className = 'toggle'

    const input = document.createElement('input')
    input.type = 'checkbox'
    input.checked = def.on
    input.addEventListener('change', () => setLayerVisible(def, input.checked))

    const sw = document.createElement('span')
    sw.className = 'switch'
    const text = document.createElement('span')
    text.className = 't-label'
    text.textContent = def.name

    // レイヤーの説明（i ボタンで開閉）
    const desc = document.createElement('div')
    desc.className = 'layer-desc'
    desc.hidden = true
    desc.textContent = def.desc

    const info = document.createElement('button')
    info.type = 'button'
    info.className = 'info-btn'
    info.textContent = 'i'
    info.setAttribute('aria-label', `${def.name}の説明`)
    info.setAttribute('aria-expanded', 'false')
    info.addEventListener('click', (e) => {
      // label 内のボタン。クリックが checkbox のトグルへ波及しないようにする
      e.preventDefault()
      e.stopPropagation()
      const open = desc.hidden
      desc.hidden = !open
      info.setAttribute('aria-expanded', String(open))
    })

    label.append(input, sw, text, info)

    // 不透明度スライダー（有効時のみ表示）
    const opac = document.createElement('div')
    opac.className = 'layer-opacity'
    opac.hidden = !def.on
    const range = document.createElement('input')
    range.type = 'range'
    range.min = '0'
    range.max = '1'
    range.step = '0.05'
    range.value = String(opacityOf(def))
    range.setAttribute('aria-label', `${def.name}の不透明度`)
    const val = document.createElement('span')
    val.className = 'op-val'
    val.textContent = `${Math.round(opacityOf(def) * 100)}%`
    range.addEventListener('input', () => {
      const v = Number(range.value)
      val.textContent = `${Math.round(v * 100)}%`
      setLayerOpacity(def, v)
    })
    opac.append(range, val)

    const legend = document.createElement('div')
    legend.className = 'layer-legend'
    legend.innerHTML = legendMarkup(def)
    legend.hidden = !def.on

    item.append(label, desc, opac, legend)
    layersDiv.append(item)
  }
}

function setLayerVisible(def: LayerDef, on: boolean): void {
  def.on = on
  if (on) ensureLayer(def)
  else removeLayer(def)
  const item = layersDiv.querySelector<HTMLElement>(`.layer-item[data-key="${def.key}"]`)
  item?.querySelector<HTMLElement>('.layer-legend')?.toggleAttribute('hidden', !on)
  item?.querySelector<HTMLElement>('.layer-opacity')?.toggleAttribute('hidden', !on)
}

function setLayerOpacity(def: LayerDef, v: number): void {
  def.opacity = v
  for (const u of opacityUpdates(def, v)) {
    if (map.getLayer(u.id)) map.setPaintProperty(u.id, u.prop, u.value)
  }
}

function setAll(on: boolean): void {
  for (const def of LAYERS) {
    if (def.on === on) continue
    const input = layersDiv.querySelector<HTMLInputElement>(`.layer-item[data-key="${def.key}"] input[type=checkbox]`)
    if (input) input.checked = on
    setLayerVisible(def, on)
  }
}
;(document.getElementById('all-on') as HTMLButtonElement).addEventListener('click', () => setAll(true))
;(document.getElementById('all-off') as HTMLButtonElement).addEventListener('click', () => setAll(false))

// ---- 背景地図スイッチャー（右下） ----
class BasemapControl implements maplibregl.IControl {
  private el!: HTMLElement
  onAdd(): HTMLElement {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl basemap-switch'
    const defs: [Basemap, string][] = [
      ['pale', '地図'],
      ['photo', '写真'],
    ]
    for (const [b, label] of defs) {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.textContent = label
      btn.dataset.base = b
      btn.setAttribute('aria-selected', String(b === base))
      btn.addEventListener('click', () => setBase(b))
      this.el.append(btn)
    }
    return this.el
  }
  onRemove(): void {
    this.el.remove()
  }
  sync(): void {
    for (const btn of this.el.querySelectorAll<HTMLButtonElement>('button')) {
      btn.setAttribute('aria-selected', String(btn.dataset.base === base))
    }
  }
}
const basemapCtrl = new BasemapControl()
map.addControl(basemapCtrl, 'bottom-right')

function setBase(next: Basemap): void {
  if (next === base) return
  base = next
  basemapCtrl.sync()
  reloadStyle()
}

// ---- ホバーカーソル（マウス環境のみ） ----
if (window.matchMedia('(hover: hover)').matches) {
  map.on('mousemove', (e) => {
    const ids = activePickIds()
    const hit = ids.length > 0 && map.queryRenderedFeatures(e.point, { layers: ids }).length > 0
    map.getCanvas().style.cursor = hit ? 'pointer' : ''
  })
}

// ---- クリックポップアップ + 黄色ハイライト ----
let popup: maplibregl.Popup | null = null
map.on('click', (e) => {
  const ids = activePickIds()
  const feats = ids.length ? map.queryRenderedFeatures(e.point, { layers: ids }) : []
  if (!feats.length) {
    // 何もない場所のクリック: 選択解除（ポップアップは closeOnClick が閉じる）
    setHighlight(null)
    return
  }
  const f = feats[0]
  const def = LAYERS.find((d) => pickLayerIdOf(d) === f.layer.id) ?? defOf('signal')
  if (!def) return
  // 前のポップアップを静かに閉じてから（close ハンドラの誤発火防止に null を先に）
  if (popup) {
    const old = popup
    popup = null
    old.remove()
  }
  setHighlight(f)
  const p = new maplibregl.Popup({ closeButton: true, maxWidth: '320px' })
    .setLngLat(e.lngLat)
    .setHTML(popupHtml(def, f.properties as Record<string, unknown>, e.lngLat.lng, e.lngLat.lat))
    .addTo(map)
  // × ボタンや地図クリックで閉じたときはハイライトも解除
  p.on('close', () => {
    if (popup === p) {
      popup = null
      setHighlight(null)
    }
  })
  popup = p
})

// ---- 診断（?debug で画面表示。実機での原因切り分け用） ----
const diagLog: string[] = []
let ctxLostCount = 0
let hudEl: HTMLElement | null = null
function diag(msg: string): void {
  const line = `${new Date().toISOString().slice(11, 19)} ${msg}`
  diagLog.push(line)
  if (diagLog.length > 8) diagLog.shift()
  console.log('[diag]', line)
  renderHud()
}
function renderHud(): void {
  if (!DEBUG || !hudEl) return
  const rows = LAYERS.filter((d) => d.on)
    .map((d) => {
      const id = pickLayerIdOf(d)
      let n = 0
      try {
        n = map.getLayer(id) ? map.queryRenderedFeatures({ layers: [id] }).length : -1
      } catch {
        n = -2
      }
      return `${d.key}: ${n}`
    })
    .join('  ')
  hudEl.innerHTML =
    `<b>build ${__BUILD_TIME__}</b><br>` +
    `zoom ${map.getZoom().toFixed(1)} · hour ${hour} · mobile ${isMobile} · ctxLost ${ctxLostCount}<br>` +
    `<u>rendered features / layer</u><br>${rows || '(none)'}<br>` +
    `<u>log</u><br>${diagLog.join('<br>')}`
}
function initHud(): void {
  if (!DEBUG) return
  hudEl = document.createElement('div')
  hudEl.id = 'diag-hud'
  document.body.append(hudEl)
  renderHud()
  map.on('render', () => {
    if (map.areTilesLoaded()) renderHud()
  })
}

// ---- 初期化 ----
const buildEl = document.getElementById('build-ver')
if (buildEl) buildEl.textContent = `build: ${__BUILD_TIME__}`
renderThemeBtn()
buildToggles()
setHour(0)
// スマホでは初期状態でパネルを畳んで地図を広く見せる
if (isMobile) panel.classList.add('collapsed')
renderCollapseBtn()
map.on('load', addDataLayers)
initHud()

// WebGL コンテキスト消失からの復帰。iOS Safari 等ではメモリ逼迫時に GL コンテキストが
// 失われ、データ層がまるごと消えて戻らないことがある。復帰時に貼り直して自動回復する。
const canvas = map.getCanvas()
canvas.addEventListener(
  'webglcontextlost',
  (e) => {
    // preventDefault しないと自動復帰イベントが発火しない
    e.preventDefault()
    ctxLostCount++
    diag('WebGL context lost')
  },
  false,
)
canvas.addEventListener(
  'webglcontextrestored',
  () => {
    diag('WebGL context restored → relayering')
    if (map.isStyleLoaded()) addDataLayers()
    else map.once('idle', addDataLayers)
  },
  false,
)

map.on('error', (e) => {
  const msg = (e && (e as unknown as { error?: Error }).error?.message) || 'map error'
  diag(`error: ${msg}`)
})

// デバッグ/外部連携用にマップを公開
;(window as unknown as { __map: maplibregl.Map }).__map = map

// PWA: Service Worker 登録（本番のみ。dev では HMR を妨げないよう無効）
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {})
  })
  // 新しい SW が制御を開始したら一度だけ再読込して最新版に切り替える
  let refreshing = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return
    refreshing = true
    window.location.reload()
  })
}
