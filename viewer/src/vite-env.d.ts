/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PMTILES_BASE?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare const __BUILD_TIME__: string
