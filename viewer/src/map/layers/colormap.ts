import type { Theme } from '../../theme'

/**
 * 平均サイクル長の配色。
 *
 * 旧配色（青→シアン→緑→黄→赤の8段）は知覚的に不均一で、段の幅も 100〜160 秒に
 * 偏っていた。実データの分布は p1=70 / p50=120 / p99=180 秒なので、下位24%が全部同じ青、
 * 上位5%が全部同じ赤になり、その内側の差が潰れていた。
 *
 * plasma は明度が単調に増えるため「明るいほど長い」が直感になり、色覚特性が異なる場合や
 * グレースケールでも順序が読める。
 */
const PLASMA = [
  '#0d0887', '#41049d', '#6a00a8', '#8f0da4', '#b12a90', '#cc4778',
  '#e16462', '#f2844b', '#fca636', '#fcce25', '#f0f921',
]

/**
 * テーマごとに使う plasma の範囲。色相の進みは共通のまま、背景とのコントラストを保つ。
 * 淡色地図では明端（淡い黄）が飛ぶので上を切り、暗い地図では暗端（ほぼ黒）が沈むので下を切る。
 */
const TRIM: Record<Theme, [number, number]> = {
  light: [0, 0.85],
  dark: [0.15, 1],
}

/**
 * 配色のドメイン（秒）。実データの p1〜p99。月ごとに変えると月間比較ができなくなるため
 * 固定し、分布が外れたときは品質ゲートで気づく。両端はクランプされる。
 */
export const CYCLE_DOMAIN = { min: 70, max: 180 } as const

/** 配色に使う段数。グラデーションバーと地図の式で同じ値を使う。 */
const STOP_COUNT = 9

function lerpChannel(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * t)
}

function hexToRgb(hex: string): [number, number, number] {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ]
}

/** plasma を [0,1] でサンプリングする。アンカー間は線形補間。 */
function plasma(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (PLASMA.length - 1)
  const i = Math.min(PLASMA.length - 2, Math.floor(x))
  const [r1, g1, b1] = hexToRgb(PLASMA[i])
  const [r2, g2, b2] = hexToRgb(PLASMA[i + 1])
  const f = x - i
  return `rgb(${lerpChannel(r1, r2, f)}, ${lerpChannel(g1, g2, f)}, ${lerpChannel(b1, b2, f)})`
}

export interface CycleStop {
  /** サイクル長（秒） */
  value: number
  color: string
}

/** ドメインを等分した配色の段。地図の interpolate 式と凡例の両方がこれを使う。 */
export function cycleRamp(theme: Theme): CycleStop[] {
  const [lo, hi] = TRIM[theme]
  const { min, max } = CYCLE_DOMAIN
  return Array.from({ length: STOP_COUNT }, (_, i) => {
    const f = i / (STOP_COUNT - 1)
    return { value: min + (max - min) * f, color: plasma(lo + (hi - lo) * f) }
  })
}

/** CSS の linear-gradient 用の色停止（凡例のグラデーションバー）。 */
export function cycleGradientCss(theme: Theme): string {
  const stops = cycleRamp(theme).map((s, i) => `${s.color} ${(i / (STOP_COUNT - 1)) * 100}%`)
  return `linear-gradient(to right, ${stops.join(', ')})`
}

/** 値（秒）→ 色。凡例のヒストグラムやポップアップのスパークラインで使う。 */
export function cycleColorAt(seconds: number, theme: Theme): string {
  const { min, max } = CYCLE_DOMAIN
  const f = Math.min(1, Math.max(0, (seconds - min) / (max - min)))
  const [lo, hi] = TRIM[theme]
  return plasma(lo + (hi - lo) * f)
}
