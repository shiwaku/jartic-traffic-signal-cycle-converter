import type { ExpressionSpecification, LayerSpecification } from 'maplibre-gl'
import sourceNames from '../../../../data/source_names.json'
import { coordFooter, esc, prop, row } from '../../lib/format'
import { sparklineSvg } from '../../lib/sparkline'
import { CYCLE_DOMAIN, cycleColorAt, cycleGradientCss, cycleRamp } from './colormap'
import type { LayerModule, PaintContext, RenderContext } from './types'

const KEY = 'signal'

/** 時間帯（0〜23時）に対応する属性名。1交差点1フィーチャで c0〜c23 に24時間分が入っている。 */
function hourKey(hour: number): string {
  return `c${hour}`
}

/** フィーチャから24時間分の値を取り出す。欠測の時間帯は null。 */
function hourlyValues(p: Record<string, unknown>): (number | null)[] {
  return Array.from({ length: 24 }, (_, h) => {
    const v = p[hourKey(h)]
    return v === undefined || v === null || v === '' ? null : Number(v)
  })
}

/**
 * 3枚の circle を重ねて「光る点」を表現する。
 * 外側ほど大きく・ぼかしを強く・薄くし、中心に白い芯を置く。
 * base はレイヤーごとの素の不透明度で、UI のスライダー値を掛けて使う。
 * radius はズームごとの半径。固定だと全国表示で塊になるので補間する。
 */
const SUBS: {
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

const layerIds = SUBS.map((s) => `${KEY}-${s.suffix}`)

/** 平均サイクル長 → 色の連続補間式。時間帯ごとに参照する属性が変わる。 */
function colorExpr(ctx: RenderContext): ExpressionSpecification {
  const stops = cycleRamp().flatMap((s) => [s.value, s.color])
  return [
    'interpolate',
    ['linear'],
    ['to-number', ['get', hourKey(ctx.hour)], CYCLE_DOMAIN.min],
    ...stops,
  ] as unknown as ExpressionSpecification
}

/** その時間帯の値を持たないフィーチャは不透明度0で消す（フィルタを触らずタイル再評価を避ける）。 */
function opacityExpr(ctx: RenderContext, value: number): ExpressionSpecification {
  return ['case', ['has', hourKey(ctx.hour)], value, 0] as unknown as ExpressionSpecification
}

function radiusExpr(stops: [number, number][]): ExpressionSpecification {
  return ['interpolate', ['linear'], ['zoom'], ...stops.flat()] as unknown as ExpressionSpecification
}

/** 情報源コード → 都道府県名（例: 3010 → 埼玉）。 */
function sourceName(code: string): string {
  return (sourceNames as Record<string, string>)[code] ?? code
}

export const signalLayer: LayerModule = {
  def: {
    key: KEY,
    name: '信号平均サイクル長',
    file: 'signal_cycle',
    sourceLayer: 'signal_cycle',
    defaultVisible: true,
    defaultOpacity: 1,
    desc: `JARTIC の交差点制御情報（${__TARGET_MONTH__}）から時間帯別に算出した、信号交差点1か所あたりの平均サイクル長（秒）。サイクル長は青・黄・赤が一巡する周期の長さで、交通量の多い交差点ほど長くなる傾向がある。`,
    attribution:
      '<a href="https://www.jartic.or.jp/" target="_blank" rel="noopener">日本道路交通情報センター[JARTIC] 交差点制御情報</a> | <a href="https://www.tmt.or.jp/research/index10.html" target="_blank" rel="noopener">日本交通管理技術協会 交差点位置情報</a>',
  },

  layerIds,
  pickLayerId: `${KEY}-glow`,

  specs(ctx: PaintContext): LayerSpecification[] {
    return SUBS.map((s) => ({
      id: `${KEY}-${s.suffix}`,
      type: 'circle',
      source: KEY,
      'source-layer': 'signal_cycle',
      paint: {
        'circle-color': s.color === 'cycle' ? colorExpr(ctx) : 'rgba(255, 255, 255, 1)',
        'circle-radius': radiusExpr(s.radius),
        'circle-blur': s.blur,
        'circle-opacity': opacityExpr(ctx, s.base * ctx.opacity),
      },
    })) as LayerSpecification[]
  },

  paintUpdates(ctx: PaintContext) {
    return SUBS.flatMap((s) => [
      {
        id: `${KEY}-${s.suffix}`,
        prop: 'circle-color',
        value: s.color === 'cycle' ? colorExpr(ctx) : 'rgba(255, 255, 255, 1)',
      },
      {
        id: `${KEY}-${s.suffix}`,
        prop: 'circle-opacity',
        value: opacityExpr(ctx, s.base * ctx.opacity),
      },
    ])
  },

  legend() {
    const { min, max } = CYCLE_DOMAIN
    // 中央の目盛りは全国の中央値（120秒）に置く。アンカーが等間隔でないので位置も実値から出す。
    const median = 120
    return {
      kind: 'gradient',
      css: cycleGradientCss(),
      ticks: [
        { pos: 0, label: `${min}秒以下` },
        { pos: ((median - min) / (max - min)) * 100, label: `${median}` },
        { pos: 100, label: `${max}秒以上` },
      ],
    }
  },

  popupHtml(p, lng, lat, ctx) {
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
    const code = prop(p, 'src')
    const rows =
      row('現在の時間帯', now === null ? 'データなし' : `${ctx.hour}時 ${now} 秒`, true) +
      (lo === null ? '' : row('最短', `${lo} 秒${at(lo)}`)) +
      (hi === null ? '' : row('最長', `${hi} 秒${at(hi)}`)) +
      row('情報源コード', code ? `${sourceName(code)}（${code}）` : '')

    const spark = sparklineSvg({
      values,
      highlight: ctx.hour,
      colorAt: (v) => cycleColorAt(v),
      label: '24時間の平均サイクル長の推移',
    })
    const axis = spark
      ? '<div class="pp-spark-axis"><span>0時</span><span>6時</span><span>12時</span><span>18時</span><span>23時</span></div>'
      : ''

    return (
      `<div class="pp-title">信号交差点 ${esc(prop(p, 'no'))}</div>` +
      `<div class="pp-sub">${esc(this.def.name)}</div>` +
      spark +
      axis +
      `<dl class="pp-dl">${rows}</dl>` +
      coordFooter(lng, lat)
    )
  },
}
