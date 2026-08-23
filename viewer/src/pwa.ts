/** PWA: Service Worker 登録（本番のみ。dev では HMR を妨げないよう無効）。 */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return

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
