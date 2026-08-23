import dataset from '../../../data/dataset.json'

/**
 * いま何を見ているのかをパネルに出す。対象年月や結合率は README にしか無く、
 * ビューワからは分からなかった。値は dataset.json（パイプラインが書く単一の情報源）から取る。
 */
export function createDatasetInfo(): void {
  const el = document.getElementById('dataset-info')
  if (!el) return

  const rows: [string, string][] = [
    ['対象年月', dataset.対象年月_表示],
    ['交差点', `${dataset.位置情報が付与された交差点数.toLocaleString('ja-JP')} 箇所`],
    ['結合率', `${dataset.行の結合率}%`],
  ]
  el.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')
}
