# -*- coding: utf-8 -*-
"""JARTIC がオープンデータとして公開している交差点制御情報（typeC）を一括ダウンロードする。

配布URLは月次で変わる（.../opendata/{更新日時}/typeC_{都市名}_{年_月}.zip）ため、
更新日時や対象年月を埋め込まず、公式のカタログ JSON から最新版を解決する。

出力:
  {out}/*.zip          ダウンロードした zip
  {out}/catalog.json   採用した typeC エントリ（対象年月・公開日・ファイル一覧）

使い方:
  python3 src/jartic_opendata_kousaten_dl.py --out work/zip
"""
import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CATALOG_URL = "https://www.jartic.or.jp/d/opendata/opendata.json"
BASE_URL = "https://www.jartic.or.jp/d/opendata"
UA = {"User-Agent": "Mozilla/5.0 (compatible; jartic-traffic-signal-cycle-converter)"}
TIMEOUT = 180   # 1ファイル最大70MB。応答が止まったら打ち切って取り直す
ATTEMPTS = 4


def fetch_catalog(url: str = CATALOG_URL) -> dict:
    """カタログJSONから交差点制御情報（typeC）のエントリを返す。"""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        catalog = json.load(r)
    for entry in catalog:
        if entry.get("type") == "typeC":
            return entry
    raise SystemExit("カタログに typeC（交差点制御情報）が見つかりません")


def download(target: dict, out_dir: Path) -> tuple[str, int]:
    """1ファイルをダウンロードする。既に同サイズで存在すればスキップ。"""
    url = BASE_URL + target["link"]
    dest = out_dir / target["link"].split("/")[-1]
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                size = int(r.headers.get("Content-Length", 0))
                if dest.exists() and dest.stat().st_size == size and size > 0:
                    return dest.name, 0
                data = r.read()
            if size and len(data) != size:
                raise OSError(f"サイズ不一致 {len(data)} != {size}")
            dest.write_bytes(data)
            return dest.name, dest.stat().st_size
        except Exception as e:
            if attempt == ATTEMPTS:
                raise SystemExit(f"{dest.name}: {ATTEMPTS}回試みて取得できませんでした（{e}）")
            wait = 2 ** attempt
            print(f"  {dest.name}: 取得失敗（{type(e).__name__}）。{wait}秒後に再試行 "
                  f"[{attempt}/{ATTEMPTS - 1}]", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise SystemExit(f"{dest.name}: 取得できませんでした")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="work/zip", help="zip の出力先")
    p.add_argument("--workers", type=int, default=4, help="並列ダウンロード数")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    entry = fetch_catalog()
    print(f"交差点制御情報 対象={entry['targetMonth']} 公開={entry['releaseDay']} "
          f"{len(entry['targetList'])}ファイル")
    (out_dir / "catalog.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

    total = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for name, size in ex.map(lambda t: download(t, out_dir), entry["targetList"]):
            total += size
            print(f"  {name}  {'スキップ（取得済）' if size == 0 else f'{size/1e6:.1f} MB'}",
                  flush=True)
    print(f"完了: {out_dir}  新規取得 {total/1e6:.0f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
