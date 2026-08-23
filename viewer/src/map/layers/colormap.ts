/**
 * 平均サイクル長の配色。
 *
 * 旧ビューワの8段階配色（青→シアン→緑→黄→赤）の色そのものを、連続グラデーションの
 * アンカーとして使う。
 *
 * 一度は知覚均等な plasma に変えたが、この地図では読みにくかった。plasma は明度が単調に
 * 変わることで順序を伝える配色で、広い面を塗るヒートマップ向けである。ここで描いているのは
 * ぼかしを掛けた小さな発光点なので、明度差はにじんで潰れ、暗端の濃紺は淡色地図にも
 * 暗色地図にも沈む。中間のマゼンタ帯も互いに似て見える。点の判別には明度差より色相差のほうが
 * 効く。「赤いほど待たされる」という直感が働くのも、この配色の実利。
 *
 * 段階（step）から連続（interpolate）に変えた点だけは戻していない。段の境目に意味がある
 * ように見えてしまうため。
 */

export interface CycleStop {
  /** この色を置くサイクル長（秒） */
  value: number
  color: string
}

/**
 * 秒数とその色。アンカーの位置は旧8段階配色の区切りをそのまま引き継いでいる
 * （100/110/120/130/140/150/160秒）。等間隔ではないので、地図の式も凡例の
 * グラデーションも、この値から位置を計算する。
 *
 * 実データの分布は p1=70 / p25=102 / p50=120 / p75=140 / p95=160 秒なので、
 * 色が変化する 100〜160 秒の区間に大半の交差点が収まる。両端はクランプされる。
 */
export const CYCLE_STOPS: CycleStop[] = [
  { value: 70, color: 'rgb(0, 127, 255)' },
  { value: 100, color: 'rgb(0, 255, 255)' },
  { value: 110, color: 'rgb(0, 255, 127)' },
  { value: 120, color: 'rgb(0, 255, 0)' },
  { value: 130, color: 'rgb(127, 255, 0)' },
  { value: 140, color: 'rgb(255, 255, 0)' },
  { value: 150, color: 'rgb(255, 127, 0)' },
  { value: 160, color: 'rgb(255, 0, 0)' },
]

/**
 * 配色のドメイン（秒）。月ごとに変えると月間比較ができなくなるため固定し、
 * 分布が外れたときは品質ゲートで気づく。
 */
export const CYCLE_DOMAIN = {
  min: CYCLE_STOPS[0].value,
  max: CYCLE_STOPS[CYCLE_STOPS.length - 1].value,
} as const

/** アンカーの位置（0〜1）。値が等間隔でないため実際の秒数から求める。 */
function offsetOf(value: number): number {
  const { min, max } = CYCLE_DOMAIN
  return (value - min) / (max - min)
}

/** 地図の interpolate 式と凡例が同じものを見るように、段はここだけで定義する。 */
export function cycleRamp(): CycleStop[] {
  return CYCLE_STOPS
}

/** CSS の linear-gradient 用の色停止（凡例のグラデーションバー）。 */
export function cycleGradientCss(): string {
  const stops = CYCLE_STOPS.map((s) => `${s.color} ${(offsetOf(s.value) * 100).toFixed(1)}%`)
  return `linear-gradient(to right, ${stops.join(', ')})`
}

function parseRgb(color: string): [number, number, number] {
  const m = /rgb\((\d+),\s*(\d+),\s*(\d+)\)/.exec(color)
  return m ? [+m[1], +m[2], +m[3]] : [0, 0, 0]
}

/** 値（秒）→ 色。ポップアップのスパークラインで使う。両端はクランプする。 */
export function cycleColorAt(seconds: number): string {
  if (seconds <= CYCLE_STOPS[0].value) return CYCLE_STOPS[0].color
  const last = CYCLE_STOPS[CYCLE_STOPS.length - 1]
  if (seconds >= last.value) return last.color
  const i = CYCLE_STOPS.findIndex((s) => s.value > seconds)
  const lo = CYCLE_STOPS[i - 1]
  const hi = CYCLE_STOPS[i]
  const f = (seconds - lo.value) / (hi.value - lo.value)
  const [r1, g1, b1] = parseRgb(lo.color)
  const [r2, g2, b2] = parseRgb(hi.color)
  const mix = (a: number, b: number): number => Math.round(a + (b - a) * f)
  return `rgb(${mix(r1, r2)}, ${mix(g1, g2)}, ${mix(b1, b2)})`
}
