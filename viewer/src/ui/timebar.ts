import hourlyStats from '../../../data/hourly_stats.json'
import { LAYERS } from '../map/layers/registry'
import { setHour, type AppStore } from '../state'
import { legendMarkup } from './legend'

/** 0→23時を巡回再生する間隔。時間帯ごとの混み具合の移り変わりを見るための機能。 */
const PLAY_INTERVAL_MS = 900

interface HourStat {
  時間帯: number
  件数: number
  p25?: number
  中央値?: number
  p75?: number
}

const STATS = hourlyStats as HourStat[]
const HOURS = 23

/** 帯が上下に貼り付かないよう、実データの範囲に少し余白を足した縦軸。 */
const Y_DOMAIN = (() => {
  const lows = STATS.flatMap((s) => (s.p25 === undefined ? [] : [s.p25]))
  const highs = STATS.flatMap((s) => (s.p75 === undefined ? [] : [s.p75]))
  if (!lows.length) return { min: 0, max: 1 }
  const min = Math.min(...lows)
  const max = Math.max(...highs)
  const pad = (max - min) * 0.08 || 1
  return { min: min - pad, max: max + pad }
})()

function y(value: number): number {
  return 100 - ((value - Y_DOMAIN.min) / (Y_DOMAIN.max - Y_DOMAIN.min)) * 100
}

/**
 * 全国の時間帯別プロファイル。p25〜p75 を帯で、中央値を線で描く。
 * viewBox を横に引き伸ばして使うので、線は vector-effect で太さを保つ。
 */
function chartMarkup(): string {
  const usable = STATS.filter((s) => s.中央値 !== undefined)
  if (usable.length < 2) return ''
  const top = usable.map((s) => `${s.時間帯},${y(s.p75 as number).toFixed(2)}`)
  const bottom = [...usable].reverse().map((s) => `${s.時間帯},${y(s.p25 as number).toFixed(2)}`)
  const median = usable.map((s) => `${s.時間帯},${y(s.中央値 as number).toFixed(2)}`)
  return (
    `<polygon class="tb-band" points="${[...top, ...bottom].join(' ')}" />` +
    `<polyline class="tb-median" points="${median.join(' ')}" vector-effect="non-scaling-stroke" />`
  )
}

/** 画面下端に常設する時間帯バー。スライダー・再生・全国プロファイル・凡例をまとめて持つ。 */
export function createTimebar(store: AppStore): void {
  const slider = document.getElementById('hour-slider') as HTMLInputElement
  const label = document.getElementById('hour-label') as HTMLOutputElement
  const stat = document.getElementById('hour-stat') as HTMLElement
  const cursor = document.getElementById('tb-cursor') as HTMLElement
  const chart = document.getElementById('tb-chart') as unknown as SVGElement
  const legend = document.getElementById('tb-legend') as HTMLElement
  const playBtn = document.getElementById('play-btn') as HTMLButtonElement
  let timer: number | null = null

  chart.innerHTML = chartMarkup()

  slider.addEventListener('input', () => setHour(store, Number(slider.value)))
  playBtn.addEventListener('click', () => store.set({ playing: !store.get().playing }))

  // 矢印キーによる時刻送りは、スライダー自身（input[type=range]）の既定動作に任せる。
  // window で拾うと、MapLibre がキャンバスで同じキーを地図のパンに使っているため
  // 「地図が動きながら時刻も動く」二重動作になる。

  function renderHour(hour: number): void {
    slider.value = String(hour)
    label.textContent = `${hour}時`
    cursor.style.left = `${(hour / HOURS) * 100}%`
    const median = STATS[hour]?.中央値
    stat.textContent = median === undefined ? '' : `全国中央値 ${median}秒`
  }

  function renderPlaying(playing: boolean): void {
    if (playing && timer === null) {
      timer = window.setInterval(() => setHour(store, store.get().hour + 1), PLAY_INTERVAL_MS)
    } else if (!playing && timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
    playBtn.textContent = playing ? '❙❙' : '▶'
    playBtn.setAttribute('aria-pressed', String(playing))
    playBtn.setAttribute('aria-label', playing ? '再生を止める' : '時間帯を順に再生')
  }

  /**
   * 連続量の凡例はここに置く。パネルを畳んでいても色の意味が読めるようにするためで、
   * ON になっている層のうち最初にグラデーション凡例を持つものを表示する。
   * カテゴリの色見本はトグルの近くにあるほうが分かりやすいのでレイヤーパネルが持つ。
   */
  function renderLegend(): void {
    const { layers, hour, theme } = store.get()
    for (const mod of LAYERS) {
      if (!layers[mod.def.key].visible) continue
      const l = mod.legend({ hour, theme })
      if (l.kind !== 'gradient') continue
      legend.innerHTML = legendMarkup(l)
      legend.hidden = false
      return
    }
    legend.hidden = true
  }

  store.subscribe((s, prev) => {
    if (s.hour !== prev.hour) renderHour(s.hour)
    if (s.playing !== prev.playing) renderPlaying(s.playing)
    if (s.layers !== prev.layers || s.theme !== prev.theme) renderLegend()
  })

  renderHour(store.get().hour)
  renderPlaying(store.get().playing)
  renderLegend()
}
