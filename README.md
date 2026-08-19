# jartic-traffic-signal-cycle-converter

日本道路交通情報センター（JARTIC）がオープンデータとして公開している[交差点制御情報](https://www.jartic.or.jp/)から、信号交差点ごと・時間帯ごとの**平均サイクル長**を算出し、PMTiles に変換して Web 地図で表示するツールです。

## Public Website
https://shiwaku.github.io/jartic-traffic-signal-cycle-converter/

## サンプル画像
![全国信号サイクル長マップ](docs/screenshot.png)

## 収録データ

<!-- dataset:begin -->
| 項目 | 内容 |
|---|---|
| 対象年月 | 2026年6月 |
| 公開日 | 2026-08-01（JARTIC） |
| 交差点数 | 10,831箇所（うち座標付与 10,543） |
| レコード数 | 259,938件（交差点 × 24時間帯） |
| 地図に載るレコード数 | 253,031件（座標を付与できた分） |
| 結合率 | 97.34%（[data/join_report.json](data/join_report.json) に情報源コード別の内訳） |
<!-- dataset:end -->

サイクル長は青・黄・赤が一巡する周期の長さで、交通量の多い交差点ほど長くなる傾向があります。

### 結合率について
交差点制御情報には座標が無く、交差点は `情報源コード + 交差点番号` でしか識別できません。座標は日本交通管理技術協会の[交差点位置情報](https://www.tmt.or.jp/research/index10.html#japanMap)から取得して結合しています。両者の収録範囲は完全には一致しないため、結合率をデータ品質の指標として `data/join_report.json` に記録し、更新のたびに差分を追えるようにしています。

<!-- lowjoin:begin -->
2026年6月時点で結合率が低い情報源コード:

| 情報源コード | 都道府県 | 制御情報 | 位置情報あり | 結合率 |
|---|---|---|---|---|
| 301C | 三重 | 328 | 159 | 48.5% |
| 3009 | 秋田 | 129 | 117 | 90.7% |
| 3010 | 埼玉 | 1,185 | 1,109 | 93.6% |
<!-- lowjoin:end -->

## データ更新

毎月1日ごろ、対象月の約2か月後に新しい月が公開されます（2026年6月分は2026年8月1日公開）。GitHub Actions の [update-data](.github/workflows/update-data.yml) が**日次でカタログJSONを見て、対象年月が変わったときだけ**取り込みを走らせるので、通常は何もする必要がありません。

```
カタログ確認 → 生zipを退避 → 集計・結合・PMTiles生成 → 品質ゲート → Release公開 → main更新 → Pages配信
```

配布URLは月次で変わる（`.../opendata/{更新日時}/typeC_{都市名}_{年_月}.zip`）ため、更新日時や対象年月はスクリプトに埋め込まず、[公式のカタログJSON](https://www.jartic.or.jp/d/opendata/opendata.json)から解決しています。対象年月・交差点数・結合率は [`data/dataset.json`](data/dataset.json) を単一の情報源とし、README のこの表もビューワの表示もそこから生成されます。

### 手元で実行する

```bash
python3 src/run_pipeline.py check      # 新しい月が出ているかだけ見る
python3 src/run_pipeline.py run        # 取得から PMTiles 生成まで通す（約20分・500MBのダウンロード）
```

`run` は品質ゲートを通ったときだけ `data/` を書き換えます。個別に実行したい場合は次のとおりです。

```bash
# 1. 交差点制御情報（typeC）を一括ダウンロード（51ファイル・約500MB）
python3 src/jartic_opendata_kousaten_dl.py --out work/zip

# 2. 時間帯別の平均サイクル長を算出（zipを展開せずストリーム処理）
python3 src/calc_average_cycle.py --zip-dir work/zip --out work

# 3. 交差点位置情報のHTMLを取得（51ページ）
python3 src/intersection_position_getHTML.py --catalog work/zip/catalog.json --out work/html

# 4. HTMLから交差点番号と座標を抽出
python3 src/HTMLtoCSV.py --catalog work/zip/catalog.json --source-codes work/source_codes.json \
    --average work/national_average_cycle.csv --html work/html --out work

# 5. 平均サイクル長に座標を付与し、GeoJSON と結合レポートを出力
python3 src/csvfile-add-latlon.py --average work/national_average_cycle.csv \
    --position work/intersection_position.csv --out work --report work/join_report.json

# 6. PMTiles を生成
tippecanoe -o work/signal_cycle.pmtiles -l signal_cycle -Z0 -z14 -r1 \
    --drop-densest-as-needed --force -P work/signal_cycle.geojsonl
```

依存は Python 3.9+ 標準ライブラリと [tippecanoe](https://github.com/felt/tippecanoe) のみです。中間ファイルは `work/` に出力され、リポジトリには含まれません。

### 品質ゲート

人のレビューを挟まずに公開するため、前回の結果と比べて次のいずれかに当たると公開を止め、Issue を立てます。

| 判定 | 内容 |
|---|---|
| 対象年月 | 前回より新しくない |
| 交差点数 | 前回比 −5% 超 |
| 行の結合率 | 前回比 −2pt 超 |
| 情報源コード | 位置情報が1件も結合できないコードがある |

しきい値は `src/run_pipeline.py run --max-intersection-drop / --max-join-rate-drop` で変えられます。

### 生データのアーカイブ

**JARTIC は最新1か月分しか配布していません**。過去月の配布URLは消えるため（実測で404）、生データは公開ウィンドウ内に取得しないと復旧できません。そのため update-data は**品質ゲートより先に**生zipを `raw-YYYYMM` の [Release](../../releases) へ退避します。ゲートに落ちても生データは残ります。

退避先は同じリポジトリなので、`GITHUB_TOKEN` だけで動きます。追加のトークンやシークレットは不要です。

手元へは、好きなタイミングで取り込めます（Release は消えないので締切はありません）。

```bash
python3 src/mirror_archive.py
# 既定の保存先は ../jartic-archive/{年月}/（環境変数 JARTIC_ARCHIVE_DIR で変更可）
# 生zip・成果物を月ごとに置き、SHA256 マニフェストを添える
```

### 各スクリプトの役割

| スクリプト | 役割 |
|---|---|
| `src/jartic_opendata_kousaten_dl.py` | カタログJSONから最新の交差点制御情報を解決して一括ダウンロード |
| `src/calc_average_cycle.py` | 制御CSVをストリーム処理し、`(情報源コード, 交差点番号, 年月, 時間帯)` ごとの平均サイクル長を算出 |
| `src/intersection_position_getHTML.py` | 日本交通管理技術協会の交差点位置情報ページを取得 |
| `src/HTMLtoCSV.py` | HTMLの `<option>` から交差点番号と座標を抽出。ページと情報源コードの対応は交差点番号の一致数で検証して決定 |
| `src/csvfile-add-latlon.py` | 平均サイクル長に座標を結合し、CSV / 行区切りGeoJSON / 結合レポートを出力 |
| `src/run_pipeline.py` | 上記を1コマンドで通し、品質ゲートを通ったものだけを `data/` に反映 |
| `src/update_docs.py` | `dataset.json` から README の収録データ節を生成 |
| `src/mirror_archive.py` | Release に退避した生データをローカルへミラー |

### データ構造上の注意
- **交差点名は交差点制御情報に含まれません**。制御CSV（時刻・情報源コード・交差点番号・サイクル長・スプリット＃1〜6・リンクバージョン）にも定義CSV（150列）にも名称の列は存在せず、交差点はコードでのみ識別されます。
- **交差点番号は情報源コードごとの連番**です。単独では一意にならないため、必ず `情報源コード + 交差点番号` を結合キーにします。
- 交差点位置情報ページの `<option value="...">` は全国通しの連番で、**交差点番号はタグのテキスト**です（例: 函館は `value=263` / テキスト `1`）。
- **情報源コードと都道府県の対応は、カタログの並び順から推測できません**。実測で `3010` は埼玉、`3011` は千葉であり、カタログの掲載順（15番目が埼玉）とは一致しません。対応は zip の中身から得た情報源コードで求め、[`data/source_names.json`](data/source_names.json) に記録しています。
- **スプリットは百分率**です。秒に直すには `サイクル長 × スプリット% ÷ 100` とします。ただし各現示の時間は青・黄・全赤を合わせた長さで、その内訳はデータに含まれません。

## ビューワ

`viewer/` は MapLibre GL JS + PMTiles のビューワ（Vite + TypeScript）です。

```bash
cd viewer
npm install
npm run dev     # http://localhost:8000/
```

dev サーバーはリポジトリ直下の `data/*.pmtiles` を Range 対応で配信します。信号サイクル長の PMTiles は月次で差し替わるためリポジトリには置かず、`data-YYYYMM` の [Release](../../releases) から配布しています。手元で動かすときは取得してください。

```bash
gh release download --pattern "signal_cycle.pmtiles" --dir data
```

`main` への push、または update-data の完了時に GitHub Actions がビューワをビルドし、最新 Release の PMTiles を同梱して GitHub Pages へ配信します。ビューワのタイトルとレイヤー説明の対象年月は `data/dataset.json` からビルド時に埋め込まれます。

機能:
- 時間帯スライダー（0〜23時）と巡回再生
- 平均サイクル長の段階配色（100秒未満〜160秒以上の8段階）
- 背景切替（国土地理院 最適化ベクトルタイル / 全国最新写真）、ライト・ダークテーマ
- レイヤーごとの表示切替・不透明度・インライン凡例
- クリックで属性ポップアップ（Google Maps / Street View リンク付き）

## ライセンス
本リポジトリのソースコードはApache License 2.0で提供されます。

本データセット（使用データ及び出力結果）はCC-BY-4.0で提供されます。使用の際には本レポジトリへのリンクを提示してください。

また、本データセットは、日本道路交通情報センター（JARTIC）がオープンデータとして公開している、[交差点制御情報](https://www.jartic.or.jp/)及び日本交通管理技術協会が公開している、[交差点位置情報](https://www.tmt.or.jp/research/index10.html#japanMap)を加工して作成したものです。本データセットの使用・加工にあたっては、[日本道路交通情報センター（JARTIC）の利用規約](https://www.jartic.or.jp/d/opendata/riyou_kiyaku.pdf)及び[日本交通管理技術協会の利用規約](https://www.tmt.or.jp/research/index10.html#japanMap)を必ずご確認ください。

人口集中地区（2020年）は[政府統計の総合窓口（e-Stat）](https://www.e-stat.go.jp/gis)の境界データを使用しています。

## 免責事項
利用者が当該データを用いて行う一切の行為について何ら責任を負うものではありません。
