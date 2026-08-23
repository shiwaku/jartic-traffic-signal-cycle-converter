import { setHour, type AppStore } from '../state'

/** 0→23時を巡回再生する間隔。時間帯ごとの混み具合の移り変わりを見るための機能。 */
const PLAY_INTERVAL_MS = 900

/** 時間帯スライダーと巡回再生。 */
export function createHourControl(store: AppStore): void {
  const slider = document.getElementById('hour-slider') as HTMLInputElement
  const label = document.getElementById('hour-label') as HTMLOutputElement
  const playBtn = document.getElementById('play-btn') as HTMLButtonElement
  let timer: number | null = null

  slider.addEventListener('input', () => setHour(store, Number(slider.value)))
  playBtn.addEventListener('click', () => store.set({ playing: !store.get().playing }))

  function renderHour(hour: number): void {
    slider.value = String(hour)
    label.textContent = `${hour}時`
  }

  function renderPlaying(playing: boolean): void {
    if (playing && timer === null) {
      timer = window.setInterval(() => setHour(store, store.get().hour + 1), PLAY_INTERVAL_MS)
    } else if (!playing && timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
    playBtn.textContent = playing ? '❙❙ 停止' : '▶ 再生'
    playBtn.setAttribute('aria-pressed', String(playing))
  }

  store.subscribe((s, prev) => {
    if (s.hour !== prev.hour) renderHour(s.hour)
    if (s.playing !== prev.playing) renderPlaying(s.playing)
  })

  renderHour(store.get().hour)
  renderPlaying(store.get().playing)
}
