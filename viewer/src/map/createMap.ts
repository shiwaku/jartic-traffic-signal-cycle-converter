import maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'

import { getBasemapStyle } from './basemap'
import { isMobile } from '../lib/env'
import type { AppState } from '../state'

const SITE_ATTRIBUTION =
  '（<a href="https://x.com/shi__works" target="_blank" rel="noopener">X</a> | <a href="https://github.com/shiwaku/jartic-traffic-signal-cycle-converter" target="_blank" rel="noopener">GitHub</a>）'

export function createMap(container: string, state: AppState): maplibregl.Map {
  const protocol = new Protocol()
  maplibregl.addProtocol('pmtiles', protocol.tile)

  const map = new maplibregl.Map({
    container,
    style: getBasemapStyle(state.basemap, state.theme),
    center: [139.6226196, 35.4660694],
    zoom: 9,
    // 地図位置を URL の #ズーム/緯度/経度 に反映（共有・リロード時の位置維持）
    hash: true,
    attributionControl: false,
    // モバイルは GPU/メモリが限られるため保持タイル数を絞る（コンテキスト消失の予防）
    maxTileCacheSize: isMobile ? 24 : undefined,
    pixelRatio: isMobile ? Math.min(window.devicePixelRatio || 1, 2) : undefined,
  })

  map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), 'top-right')
  map.addControl(new maplibregl.FullscreenControl(), 'top-right')
  map.addControl(
    new maplibregl.GeolocateControl({
      positionOptions: { enableHighAccuracy: false },
      fitBoundsOptions: { maxZoom: 18 },
      trackUserLocation: true,
      showUserLocation: true,
    }),
    'top-right',
  )
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 200, unit: 'metric' }), 'bottom-left')
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: SITE_ATTRIBUTION }))

  return map
}
