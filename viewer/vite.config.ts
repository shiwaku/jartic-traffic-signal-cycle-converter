import { defineConfig, type Plugin } from 'vite'
import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs'
import { join, normalize, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))
// PMTiles はリポジトリ直下 data/ に置かれている（本番は Release から取得して dist に同梱）。
const PMTILES_DIR = resolve(rootDir, '..', 'data')

/**
 * 収録データのメタデータ。対象年月を各所に書き写すと、データだけ更新して文言が古いまま
 * 残るため、パイプラインが書く data/dataset.json を単一の情報源にしてビルド時に流し込む。
 */
const dataset = JSON.parse(
  readFileSync(resolve(rootDir, '..', 'data', 'dataset.json'), 'utf-8'),
) as { 対象年月_表示: string; 公開日: string }
const TARGET_MONTH = dataset.対象年月_表示

/** index.html の %TARGET_MONTH% を対象年月に置き換える。 */
function datasetHtml(): Plugin {
  return {
    name: 'dataset-html',
    transformIndexHtml(html) {
      return html.replaceAll('%TARGET_MONTH%', TARGET_MONTH)
    },
  }
}

/**
 * 開発サーバーで data/*.pmtiles を Range(206) 対応で配信するミドルウェア。
 * pmtiles.js は HTTP Byte Serving を要求するため、これがないとタイルを読めない。
 * 本番（GitHub Pages）では PMTiles を同梱し、静的ホストが Range を処理する。
 */
function pmtilesDevServer(): Plugin {
  return {
    name: 'pmtiles-dev-server',
    configureServer(server) {
      server.middlewares.use('/pmtiles', (req, res, next) => {
        try {
          const urlPath = decodeURIComponent((req.url ?? '').split('?')[0])
          const rel = normalize(urlPath).replace(/^([/\\]|\.\.[/\\])+/, '')
          const file = join(PMTILES_DIR, rel)
          if (!file.startsWith(PMTILES_DIR) || !existsSync(file)) {
            res.statusCode = 404
            res.end('Not found')
            return
          }
          const size = statSync(file).size
          res.setHeader('Accept-Ranges', 'bytes')
          res.setHeader('Access-Control-Allow-Origin', '*')
          res.setHeader('Content-Type', 'application/octet-stream')

          const range = req.headers.range
          const m = range ? /bytes=(\d*)-(\d*)/.exec(range) : null
          if (m) {
            const start = m[1] ? parseInt(m[1], 10) : 0
            let end = m[2] ? parseInt(m[2], 10) : size - 1
            end = Math.min(end, size - 1)
            if (start > end || start >= size) {
              res.statusCode = 416
              res.setHeader('Content-Range', `bytes */${size}`)
              res.end()
              return
            }
            res.statusCode = 206
            res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`)
            res.setHeader('Content-Length', String(end - start + 1))
            createReadStream(file, { start, end }).pipe(res)
            return
          }

          res.statusCode = 200
          res.setHeader('Content-Length', String(size))
          createReadStream(file).pipe(res)
        } catch (err) {
          next(err)
        }
      })
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [pmtilesDevServer(), datasetHtml()],
  server: { port: 8000 },
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC'),
    __TARGET_MONTH__: JSON.stringify(TARGET_MONTH),
  },
})
