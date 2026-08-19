/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PMTILES_BASE?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare const __BUILD_TIME__: string
/** 収録データの対象年月（data/dataset.json 由来。ビルド時に埋め込まれる） */
declare const __TARGET_MONTH__: string
