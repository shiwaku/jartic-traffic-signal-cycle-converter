import type { ExpressionSpecification, LayerSpecification } from 'maplibre-gl'
import sourceNames from '../../data/source_names.json'
import { CYCLE_DOMAIN, cycleColorAt, cycleGradientCss, cycleRamp } from './colormap'
import type { Theme } from './theme'

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

/** 描画コンテキスト。時間帯とテーマで見た目が変わる。 */
export interface PaintContext {
  hour: number
  theme: Theme
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
    desc: `JARTIC の交差点制御情報（${__TARGET_MONTH__}）から時間帯別に算出した、信号交差点1か所あたりの平均サイクル長（秒）。サイクル長は青・黄・赤が一巡する周期の長さで、交通量の多い交差点ほど長くなる傾向がある。`,
    attribution:
      '<a href="https://www.jartic.or.jp/" target="_blank" rel="noopener">日本道路交通情報センター[JARTIC] 交差点制御情報</a> | <a href="https://www.tmt.or.jp/research/index10.html" target="_blank" rel="noopener">日本交通管理技術協会 交差点位置情報</a>',
  },
]

export function opacityOf(def: LayerDef): number {
  return def.opacity ?? def.defaultOpacity
}

// ---- 属性 ----

/** 時間帯（0〜23時）に対応する属性名。1交差点1フィーチャで c0〜c23 に24時間分が入っている。 */
export function hourKey(hour: number): string {
  return `c${hour}`
}

/** フィーチャから24時間分の値を取り出す。欠測の時間帯は null。 */
export function hourlyValues(p: Record<string, unknown>): (number | null)[] {
  return Array.from({ length: 24 }, (_, h) => {
    const v = p[hourKey(h)]
    return v === undefined || v === null || v === '' ? null : Number(v)
  })
}

// ---- レイヤー定義 ----

/**
 * 信号サイクルは3枚の circle を重ねて「光る点」を表現する。
 * 外側ほど大きく・ぼかしを強く・薄くし、中心に白い芯を置く。
 * base はレイヤーごとの素の不透明度で、UI のスライダー値を掛けて使う。
 * radius はズームごとの半径。固定だと全国表示で塊になるので補間する。
 */
const SIGNAL_SUBS: {
  suffix: string
  radius: [number, number][]
  blur: number
  base: number
  color: 'cycle' | 'white'
}[] = [
  { suffix: 'glow', radius: [[4, 5], [9, 11], [13, 18]], blur: 2.5, base: 0.6, color: 'cycle' },
  { suffix: 'mid', radius: [[4, 2.5], [9, 5.5], [13, 9]], blur: 1.5, base: 0.8, color: 'cycle' },
  { suffix: 'core', radius: [[4, 0.6], [9, 1], [13, 1.5]], blur: 0, base: 1, color: 'white' },
]

/** 平均サイクル長 → 色の連続補間式。時間帯ごとに参照する属性が変わる。 */
function cycleColorExpr(ctx: PaintContext): ExpressionSpecification {
  const stops = cycleRamp(ctx.theme).flatMap((s) => [s.value, s.color])
  return [
    'interpolate',
    ['linear'],
    ['to-number', ['get', hourKey(ctx.hour)], CYCLE_DOMAIN.min],
    ...stops,
  ] as unknown as ExpressionSpecification
}

/** その時間帯の値を持たないフィーチャは不透明度0で消す（フィルタを触らずタイル再評価を避ける）。 */
function cycleOpacityExpr(ctx: PaintContext, value: number): ExpressionSpecification {
  return ['case', ['has', hourKey(ctx.hour)], value, 0] as unknown as ExpressionSpecification
}

function radiusExpr(stops: [number, number][]): ExpressionSpecification {
  return ['interpolate', ['linear'], ['zoom'], ...stops.flat()] as unknown as ExpressionSpecification
}

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
export function layerSpecs(def: LayerDef, ctx: PaintContext): LayerSpecification[] {
  const v = opacityOf(def)
  if (def.key === 'signal') {
    return SIGNAL_SUBS.map((s) => ({
      id: `signal-${s.suffix}`,
      type: 'circle',
      source: def.key,
      'source-layer': def.sourceLayer,
      paint: {
        'circle-color': s.color === 'cycle' ? cycleColorExpr(ctx) : 'rgba(255, 255, 255, 1)',
        'circle-radius': radiusExpr(s.radius),
        'circle-blur': s.blur,
        'circle-opacity': cycleOpacityExpr(ctx, s.base * v),
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

export interface PaintUpdate {
  id: string
  prop: string
  value: unknown
}

/**
 * 現在の時間帯・テーマ・不透明度を paint に反映する更新の一覧。
 * 時間帯の切替は setFilter ではなくこれで行う。フィルタを変えるとタイルの再評価が走るが、
 * paint プロパティの差し替えなら再評価が起きない。
 */
export function paintUpdates(def: LayerDef, ctx: PaintContext): PaintUpdate[] {
  const v = opacityOf(def)
  if (def.key === 'signal') {
    return SIGNAL_SUBS.flatMap((s) => [
      {
        id: `signal-${s.suffix}`,
        prop: 'circle-color',
        value: s.color === 'cycle' ? cycleColorExpr(ctx) : 'rgba(255, 255, 255, 1)',
      },
      {
        id: `signal-${s.suffix}`,
        prop: 'circle-opacity',
        value: cycleOpacityExpr(ctx, s.base * v),
      },
    ])
  }
  return [{ id: `${def.key}-lyr`, prop: 'fill-opacity', value: v }]
}

// ---- 凡例 ----

export interface SwatchItem {
  color: string
  label: string
  shape: 'circle' | 'square'
}

export type Legend =
  | { kind: 'gradient'; css: string; ticks: { pos: number; label: string }[] }
  | { kind: 'items'; items: SwatchItem[] }

export function legendFor(def: LayerDef, ctx: PaintContext): Legend {
  if (def.key === 'signal') {
    const { min, max } = CYCLE_DOMAIN
    const mid = (min + max) / 2
    return {
      kind: 'gradient',
      css: cycleGradientCss(ctx.theme),
      ticks: [
        { pos: 0, label: `${min}秒以下` },
        { pos: 50, label: `${mid}` },
        { pos: 100, label: `${max}秒以上` },
      ],
    }
  }
  return { kind: 'items', items: [{ color: 'rgba(255, 191, 0, 0.6)', label: def.name, shape: 'square' }] }
}

// ---- ポップアップ ----

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)
}

const S = (p: Record<string, unknown>, k: string): string => {
  const v = p[k]
  return v === undefined || v === null || v === '' ? '' : String(v)
}

/** 情報源コード → 都道府県名（例: 3010 → 埼玉）。 */
function sourceName(code: string): string {
  return (sourceNames as Record<string, string>)[code] ?? code
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

const SPARK_W = 264
const SPARK_H = 56
const SPARK_PAD = 6

/**
 * 24時間の推移を折れ線で描く。1交差点1フィーチャにしたことで、クリックした地点の
 * 1日分の値がその場に揃っている。現在の時間帯には印を置く。
 */
function sparklineSvg(values: (number | null)[], hour: number, theme: Theme): string {
  const present = values.filter((v): v is number => v !== null)
  if (present.length < 2) return ''
  const lo = Math.min(...present)
  const hi = Math.max(...present)
  const span = hi - lo || 1
  const x = (h: number): number => SPARK_PAD + (h / 23) * (SPARK_W - SPARK_PAD * 2)
  const y = (v: number): number =>
    SPARK_H - SPARK_PAD - ((v - lo) / span) * (SPARK_H - SPARK_PAD * 2)

  // 欠測で線を切るため、連続している区間ごとに polyline を分ける
  const segments: string[][] = []
  let current: string[] = []
  values.forEach((v, h) => {
    if (v === null) {
      if (current.length) segments.push(current)
      current = []
      return
    }
    current.push(`${x(h).toFixed(1)},${y(v).toFixed(1)}`)
  })
  if (current.length) segments.push(current)

  const lines = segments
    .filter((s) => s.length > 1)
    .map((s) => `<polyline class="spark-line" points="${s.join(' ')}" />`)
    .join('')
  const dots = values
    .map((v, h) =>
      v === null
        ? ''
        : `<circle cx="${x(h).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${h === hour ? 3.5 : 1.4}"` +
          ` fill="${cycleColorAt(v, theme)}"${h === hour ? ' class="spark-now"' : ''} />`,
    )
    .join('')
  const guide =
    values[hour] === null
      ? ''
      : `<line class="spark-guide" x1="${x(hour).toFixed(1)}" y1="${SPARK_PAD - 3}" ` +
        `x2="${x(hour).toFixed(1)}" y2="${SPARK_H - SPARK_PAD + 3}" />`

  return (
    `<svg class="pp-spark" viewBox="0 0 ${SPARK_W} ${SPARK_H}" width="${SPARK_W}" height="${SPARK_H}" ` +
    `role="img" aria-label="24時間の平均サイクル長の推移">${guide}${lines}${dots}</svg>` +
    `<div class="pp-spark-axis"><span>0時</span><span>6時</span><span>12時</span><span>18時</span><span>23時</span></div>`
  )
}

export function popupHtml(
  def: LayerDef,
  p: Record<string, unknown>,
  lng: number,
  lat: number,
  ctx: PaintContext,
): string {
  if (def.key === 'signal') {
    const values = hourlyValues(p)
    const now = values[ctx.hour]
    const present = values.filter((v): v is number => v !== null)
    const lo = present.length ? Math.min(...present) : null
    const hi = present.length ? Math.max(...present) : null
    // 最短・最長は同じ値が何時間も続くことがある（例: 7〜22時がずっと130秒）。
    // 先頭の1時間だけを出すとそこだけが極値のように読めるので、複数あるときはそう書く。
    const at = (target: number): string => {
      const hours = values.flatMap((v, h) => (v === target ? [h] : []))
      if (!hours.length) return ''
      return hours.length === 1 ? `（${hours[0]}時）` : `（${hours[0]}時ほか${hours.length - 1}時間）`
    }
    const code = S(p, 'src')
    const rows =
      row('現在の時間帯', now === null ? 'データなし' : `${ctx.hour}時 ${now} 秒`, true) +
      (lo === null ? '' : row('最短', `${lo} 秒${at(lo)}`)) +
      (hi === null ? '' : row('最長', `${hi} 秒${at(hi)}`)) +
      row('情報源コード', code ? `${sourceName(code)}（${code}）` : '')
    return (
      `<div class="pp-title">信号交差点 ${esc(S(p, 'no'))}</div>` +
      `<div class="pp-sub">${esc(def.name)}</div>` +
      sparklineSvg(values, ctx.hour, ctx.theme) +
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
