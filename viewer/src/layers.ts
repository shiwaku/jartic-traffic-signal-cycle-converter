import type { ExpressionSpecification, FilterSpecification, LayerSpecification } from 'maplibre-gl'

export interface LayerDef {
  /** UI・ソース ID。 */
  key: string
  /** 表示名（日本語） */
  name: string
  /** リポジトリ直下 data/ の PMTiles ファイル名（拡張子なし） */
  file: string
  /** ベクトルタイル内のレイヤー名（PMTiles のメタデータに記録された値） */
  sourceLayer: string
  /** 初期表示 ON/OFF */
  on: boolean
  /** 既定の不透明度。UI のスライダーで変更される。 */
  defaultOpacity: number
  /** 現在の不透明度（未指定なら defaultOpacity） */
  opacity?: number
  /** レイヤーの説明（パネルの i ボタンで表示） */
  desc: string
  attribution: string
}

/**
 * 描画対象レイヤー。パネルの並び順（先頭＝一番上）。
 * main.ts の addDataLayers がこの配列順に addLayer するため、**配列末尾ほど地図で最前面**。
 * 面である人口集中地区を背面に、点である信号サイクルを前面に置く。
 */
export const LAYERS: LayerDef[] = [
  {
    key: 'did',
    name: '人口集中地区（2020年）',
    file: '2020_did_ddsw_01-47_JGD2011',
    sourceLayer: '2020_did_ddsw_0147_JGD2011fgb',
    on: true,
    defaultOpacity: 0.2,
    desc: '国勢調査の基本単位区等を基礎とし、人口密度が1平方キロメートルあたり4,000人以上の基本単位区等が市区町村の区域内で互いに隣接して人口が5,000人以上となる地区。市街地の広がりを示す指標として用いられる。',
    attribution:
      '<a href="https://www.e-stat.go.jp/gis" target="_blank" rel="noopener">政府統計の総合窓口[e-Stat] 人口集中地区（2020年）</a>',
  },
  {
    key: 'signal',
    name: '信号平均サイクル長',
    file: 'signal_cycle',
    sourceLayer: 'signal_cycle',
    on: true,
    defaultOpacity: 1,
    desc: 'JARTIC の交差点制御情報（2023年2月）から時間帯別に算出した、信号交差点1か所あたりの平均サイクル長（秒）。サイクル長は青・黄・赤が一巡する周期の長さで、交通量の多い交差点ほど長くなる傾向がある。',
    attribution:
      '<a href="https://www.jartic.or.jp/" target="_blank" rel="noopener">日本道路交通情報センター[JARTIC] 交差点制御情報</a> | <a href="https://www.tmt.or.jp/research/index10.html" target="_blank" rel="noopener">日本交通管理技術協会 交差点位置情報</a>',
  },
]

export function opacityOf(def: LayerDef): number {
  return def.opacity ?? def.defaultOpacity
}

// ---- 配色（平均サイクル長の段階色。旧ビューワの配色を踏襲） ----

export interface CycleStop {
  /** この色を使う下限値（秒）。先頭は下限なし。 */
  min: number
  color: string
  label: string
}

export const CYCLE_STOPS: CycleStop[] = [
  { min: 0, color: 'rgba(0, 127, 255, 1)', label: '100秒未満' },
  { min: 100, color: 'rgba(0, 255, 255, 1)', label: '100秒以上110秒未満' },
  { min: 110, color: 'rgba(0, 255, 127, 1)', label: '110秒以上120秒未満' },
  { min: 120, color: 'rgba(0, 255, 0, 1)', label: '120秒以上130秒未満' },
  { min: 130, color: 'rgba(127, 255, 0, 1)', label: '130秒以上140秒未満' },
  { min: 140, color: 'rgba(255, 255, 0, 1)', label: '140秒以上150秒未満' },
  { min: 150, color: 'rgba(255, 127, 0, 1)', label: '150秒以上160秒未満' },
  { min: 160, color: 'rgba(255, 0, 0, 1)', label: '160秒以上' },
]

/** 平均サイクル長 → 段階色の step 式。 */
function cycleColor(): ExpressionSpecification {
  const rest: (number | string)[] = []
  for (const s of CYCLE_STOPS.slice(1)) rest.push(s.min, s.color)
  const expr = ['step', ['to-number', ['get', '平均サイクル長'], 0], CYCLE_STOPS[0].color, ...rest]
  return expr as unknown as ExpressionSpecification
}

// ---- レイヤー定義 ----

/**
 * 信号サイクルは3枚の circle を重ねて「光る点」を表現する。
 * 外側ほど大きく・ぼかしを強く・薄くし、中心に白い芯を置く。
 * base はレイヤーごとの素の不透明度で、UI のスライダー値を掛けて使う。
 */
const SIGNAL_SUBS: { suffix: string; radius: number; blur: number; base: number; color: 'cycle' | 'white' }[] = [
  { suffix: 'glow', radius: 18, blur: 2.5, base: 0.6, color: 'cycle' },
  { suffix: 'mid', radius: 9, blur: 1.5, base: 0.8, color: 'cycle' },
  { suffix: 'core', radius: 1, blur: 0, base: 1, color: 'white' },
]

/** 地図に追加するレイヤー ID を、描画順（背面→前面）で返す。 */
export function layerIdsOf(def: LayerDef): string[] {
  if (def.key === 'signal') return SIGNAL_SUBS.map((s) => `signal-${s.suffix}`)
  return [`${def.key}-lyr`]
}

/** クリック・ホバー判定に使うレイヤー ID（当たり判定が最も広いもの）。 */
export function pickLayerIdOf(def: LayerDef): string {
  return def.key === 'signal' ? 'signal-glow' : `${def.key}-lyr`
}

/** 地図に追加するレイヤー仕様を、描画順（背面→前面）で返す。 */
export function layerSpecs(def: LayerDef): LayerSpecification[] {
  const v = opacityOf(def)
  if (def.key === 'signal') {
    return SIGNAL_SUBS.map((s) => ({
      id: `signal-${s.suffix}`,
      type: 'circle',
      source: def.key,
      'source-layer': def.sourceLayer,
      paint: {
        'circle-color': s.color === 'cycle' ? cycleColor() : 'rgba(255, 255, 255, 1)',
        'circle-radius': s.radius,
        'circle-blur': s.blur,
        'circle-opacity': s.base * v,
      },
    })) as LayerSpecification[]
  }
  return [
    {
      id: `${def.key}-lyr`,
      type: 'fill',
      source: def.key,
      'source-layer': def.sourceLayer,
      paint: { 'fill-color': 'rgb(255, 191, 0)', 'fill-opacity': v },
    } as LayerSpecification,
  ]
}

/** 不透明度スライダーの反映。レイヤー種別ごとに対象プロパティが違う。 */
export function opacityUpdates(def: LayerDef, v: number): { id: string; prop: string; value: number }[] {
  if (def.key === 'signal') {
    return SIGNAL_SUBS.map((s) => ({ id: `signal-${s.suffix}`, prop: 'circle-opacity', value: s.base * v }))
  }
  return [{ id: `${def.key}-lyr`, prop: 'fill-opacity', value: v }]
}

// ---- 時間帯フィルタ ----

/** 時間帯（0〜23時）→ 属性「時間帯」（"HH:00" 形式）の一致フィルタ。 */
export function hourFilter(hour: number): FilterSpecification {
  const hh = String(hour).padStart(2, '0')
  return ['==', ['get', '時間帯'], `${hh}:00`] as unknown as FilterSpecification
}

/** 時間帯フィルタを適用するレイヤー（信号サイクルのみ）。 */
export function hourFilteredLayerIds(): string[] {
  return SIGNAL_SUBS.map((s) => `signal-${s.suffix}`)
}

// ---- 凡例 ----

export interface LegendItem {
  color: string
  label: string
  shape: 'circle' | 'square'
}

export function legendFor(def: LayerDef): LegendItem[] {
  if (def.key === 'signal') {
    return CYCLE_STOPS.map((s) => ({ color: s.color, label: s.label, shape: 'circle' as const }))
  }
  return [{ color: 'rgba(255, 191, 0, 0.6)', label: def.name, shape: 'square' as const }]
}

// ---- ポップアップ ----

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)
}

const S = (p: Record<string, unknown>, k: string): string => {
  const v = p[k]
  return v === undefined || v === null || v === '' ? '' : String(v)
}

// 人口集中地区の属性名（e-Stat 境界データ）→ 和名。
const DID_LABELS: Record<string, string> = {
  KEN: '都道府県コード',
  CITY: '市区町村コード',
  CITYNAME: '市区町村名',
  CLASS: '区分',
  JINKO: '人口',
  MENSEKI: '面積(km²)',
}

/** 属性表の1行。 */
function row(label: string, value: string, strong = false): string {
  if (!value) return ''
  return `<dt>${esc(label)}</dt><dd${strong ? ' class="pp-strong"' : ''}>${esc(value)}</dd>`
}

/** クリック地点の座標と外部地図サービスへのリンク。 */
function footHtml(lng: number, lat: number): string {
  const q = `${lat},${lng}`
  return (
    `<div class="pp-foot">座標: ${lat.toFixed(7)}, ${lng.toFixed(7)}（クリック位置）<br />` +
    `<a href="https://www.google.com/maps?q=${q}&hl=ja" target="_blank" rel="noopener">🌎 Google Maps</a> ` +
    `<a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${q}&hl=ja" target="_blank" rel="noopener">📷 Street View</a></div>`
  )
}

export function popupHtml(def: LayerDef, p: Record<string, unknown>, lng: number, lat: number): string {
  if (def.key === 'signal') {
    const cycle = S(p, '平均サイクル長')
    const rows =
      row('情報源コード', S(p, '情報源コード')) +
      row('交差点番号', S(p, '交差点番号')) +
      row('年月', S(p, '年月')) +
      row('時間帯', S(p, '時間帯')) +
      row('平均サイクル長', cycle ? `${Math.round(Number(cycle) * 10) / 10} 秒` : '', true)
    return (
      `<div class="pp-title">信号交差点 ${esc(S(p, '交差点番号'))}</div>` +
      `<div class="pp-sub">${esc(def.name)}</div>` +
      `<dl class="pp-dl">${rows}</dl>` +
      footHtml(lng, lat)
    )
  }

  const rows = Object.entries(DID_LABELS)
    .map(([k, label]) => row(label, S(p, k)))
    .join('')
  return (
    `<div class="pp-title">${esc(S(p, 'CITYNAME') || def.name)}</div>` +
    `<div class="pp-sub">${esc(def.name)}</div>` +
    (rows ? `<dl class="pp-dl">${rows}</dl>` : '') +
    footHtml(lng, lat)
  )
}
