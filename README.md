# jartic-traffic-signal-cycle-converter
## Public Website
https://shiwaku.github.io/jartic-traffic-signal-cycle-converter/
## サンプル画像
![image](https://user-images.githubusercontent.com/71203808/234752923-71deb437-b846-4268-9f20-84f1b78d3833.png)

# データの取得
## 交差点制御情報
### jartic_opendata_kousaten_dl.py
- 日本道路交通情報センター（JARTIC）がオープンデータとして公開している、[交差点制御情報（zip形式）](https://www.jartic.or.jp/)を一括でダウンロードするプログラムです。
#### 使用データ
- `kousaten_PrefRoman.csv`（本リポジトリに同梱）
#### 出力結果
- 交差点制御情報（zip形式）一式、約286.7MB（2023年4月3日 09:11 時点のデータ）

# データの加工
## 交差点制御情報
### calc_average_cycle.py
- [交差点制御情報（csv形式）](https://www.jartic.or.jp/)をもとに、信号の平均サイクル長を算出するプログラムです。
#### 使用データ
- 交差点制御情報
- zipファイルをcsvファイルに解凍したものを使用
- ファイル名に「制御」の記載のあるcsvファイルを使用
#### 出力結果
- 都道府県別の平均サイクル長（csv形式）、計415.1KB

### csvfile-merge.py
- 算出した、47都道府県の平均サイクル長（csv形式）をマージするプログラムです。
#### 出力結果
- `national_Control_202302_Average_Cycle.csv`、7.2MB

### csvfile-add-latlon.py
- マージ済みの平均サイクル長（csv形式）に信号交差点の位置座標を付与するプログラムです。
#### 使用データ
- `national_Control_202302_Average_Cycle.csv`、7.2MB
- `intersection_position.csv`、668.7KB ※後述の交差点位置情報
#### 出力結果
- `signal_cycle.csv`、13.3MB
- ※参考1（csvファイルをgeojsonファイルに変換したもの）`signal_cycle.geojson`、61.3MB
- ※参考2（geojsonファイルをpmtilesファイルに変換したもの）`data/signal_cycle.pmtiles`、20.5MB（本リポジトリに同梱）

## 交差点位置情報
### intersection_position_getHTML.py
- [日本交通管理技術協会のWebサイト](https://www.tmt.or.jp/research/index10.html#japanMap)からhtmlファイルを一括でダウンロードするプログラムです。

### HTMLtoCSV.py
- ダウンロードした、htmlファイルの中から座標及び交差点番号を取得し、csvファイルに出力するプログラムです。
#### 使用データ
- `htmlファイル一式`
- 情報源コード一覧
- 日本道路交通情報センター（JARTIC）が公開している、[交差点制御情報の説明書](https://www.jartic.or.jp/)に記載の情報源コード一覧から作成したデータです。`source_code_information.csv`、2.4KB
#### 出力結果
- `intersection_position.csv`、668.7KB

# ライセンス
本リポジトリのソースコードはApache License 2.0で提供されます。

本データセット（使用データ及び出力結果）はCC-BY-4.0で提供されます。使用の際には本レポジトリへのリンクを提示してください。

また、本データセットは、日本道路交通情報センター（JARTIC）がオープンデータとして公開している、[交差点制御情報](https://www.jartic.or.jp/)及び日本交通管理技術協会が公開している、[交差点位置情報](https://www.tmt.or.jp/research/index10.html#japanMap)を加工して作成したものです。本データセットの使用・加工にあたっては、[日本道路交通情報センター（JARTIC）の利用規約](https://www.jartic.or.jp/d/opendata/riyou_kiyaku.pdf)及び[日本交通管理技術協会の利用規約](https://www.tmt.or.jp/research/index10.html#japanMap)を必ずご確認ください。

# 免責事項
利用者が当該データを用いて行う一切の行為について何ら責任を負うものではありません。
