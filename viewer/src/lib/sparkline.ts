const W = 264
const H = 56
const PAD = 6

export interface SparklineOptions {
  /** 24個の値。欠測は null（線を切る）。 */
  values: (number | null)[]
  /** 強調する位置（現在の時間帯） */
  highlight: number
  /** 値 → 点の色 */
  colorAt: (value: number) => string
  /** 読み上げ用のラベル */
  label: string
}

/**
 * 1日分の推移を折れ線で描く。1交差点1フィーチャにしたことで、クリックした地点の
 * 24時間分がその場に揃っている。値が2点未満のときは何も描かない。
 */
export function sparklineSvg(o: SparklineOptions): string {
  const present = o.values.filter((v): v is number => v !== null)
  if (present.length < 2) return ''
  const lo = Math.min(...present)
  const hi = Math.max(...present)
  const span = hi - lo || 1
  const last = o.values.length - 1
  const x = (i: number): number => PAD + (i / last) * (W - PAD * 2)
  const y = (v: number): number => H - PAD - ((v - lo) / span) * (H - PAD * 2)

  // 欠測で線を切るため、連続している区間ごとに polyline を分ける
  const segments: string[][] = []
  let current: string[] = []
  o.values.forEach((v, i) => {
    if (v === null) {
      if (current.length) segments.push(current)
      current = []
      return
    }
    current.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`)
  })
  if (current.length) segments.push(current)

  const lines = segments
    .filter((s) => s.length > 1)
    .map((s) => `<polyline class="spark-line" points="${s.join(' ')}" />`)
    .join('')
  const dots = o.values
    .map((v, i) =>
      v === null
        ? ''
        : `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${i === o.highlight ? 3.5 : 1.4}"` +
          ` fill="${o.colorAt(v)}"${i === o.highlight ? ' class="spark-now"' : ''} />`,
    )
    .join('')
  const guide =
    o.values[o.highlight] === null
      ? ''
      : `<line class="spark-guide" x1="${x(o.highlight).toFixed(1)}" y1="${PAD - 3}" ` +
        `x2="${x(o.highlight).toFixed(1)}" y2="${H - PAD + 3}" />`

  return (
    `<svg class="pp-spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" ` +
    `role="img" aria-label="${o.label}">${guide}${lines}${dots}</svg>`
  )
}
