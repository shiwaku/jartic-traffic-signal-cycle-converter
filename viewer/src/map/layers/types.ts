import type { LayerSpecification } from 'maplibre-gl'
import type { Theme } from '../../theme'

/** レイヤーの不変な定義。表示状態（ON/OFF・不透明度）は state 側が持つ。 */
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
  defaultVisible: boolean
  /** 初期の不透明度 */
  defaultOpacity: number
  /** レイヤーの説明（パネルの i ボタンで表示） */
  desc: string
  attribution: string
}

/** 見え方を決める文脈。 */
export interface RenderContext {
  hour: number
  theme: Theme
}

export interface PaintContext extends RenderContext {
  opacity: number
}

export interface PaintUpdate {
  id: string
  prop: string
  value: unknown
}

export interface SwatchItem {
  color: string
  label: string
  shape: 'circle' | 'square'
}

export type Legend =
  | { kind: 'gradient'; css: string; ticks: { pos: number; label: string }[] }
  | { kind: 'items'; items: SwatchItem[] }

/**
 * 1レイヤーの全て（定義・描画仕様・凡例・ポップアップ）をまとめたもの。
 * レイヤーを増やすときは、このかたちのモジュールを1枚書いて registry に足すだけでよい。
 */
export interface LayerModule {
  def: LayerDef
  /** 地図に載せるレイヤー ID。描画順（背面→前面）。 */
  layerIds: string[]
  /** クリック・ホバー判定に使うレイヤー ID（当たり判定が最も広いもの）。 */
  pickLayerId: string
  specs(ctx: PaintContext): LayerSpecification[]
  paintUpdates(ctx: PaintContext): PaintUpdate[]
  legend(ctx: RenderContext): Legend
  popupHtml(properties: Record<string, unknown>, lng: number, lat: number, ctx: RenderContext): string
}
