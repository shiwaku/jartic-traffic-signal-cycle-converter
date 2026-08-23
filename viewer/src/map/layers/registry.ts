import { didLayer } from './did'
import { signalLayer } from './signal'
import type { LayerModule } from './types'

/**
 * 描画対象レイヤー。パネルの並び順（先頭＝一番上）。
 * dataLayers がこの配列順に addLayer するため、**配列末尾ほど地図で最前面**。
 * 面である人口集中地区を背面に、点である信号サイクルを前面に置く。
 *
 * レイヤーを増やすときは、layers/ にモジュールを1枚書いてこの配列に足すだけでよい。
 */
export const LAYERS: LayerModule[] = [didLayer, signalLayer]

export function layerByKey(key: string): LayerModule | undefined {
  return LAYERS.find((m) => m.def.key === key)
}

export function layerByPickId(id: string): LayerModule | undefined {
  return LAYERS.find((m) => m.pickLayerId === id)
}
