# -*- coding: utf-8 -*-
"""日本交通管理技術協会のWebサイトから交差点位置情報のHTMLを一括ダウンロードする。

ページは都道府県ごと（北海道のみ方面別に5ページ）に分かれており、JARTIC のカタログ
（typeC の targetList の id: R01_1 / R02 …）と1対1で対応する。カタログ側の id から
ページ名 index10_{都道府県番号}[_{方面番号}].html を組み立てて取得する。

出力:
  {out}/index10_*.html

使い方:
  python3 src/intersection_position_getHTML.py --catalog work/zip/catalog.json --out work/html
"""
import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_URL = "https://www.tmt.or.jp/research"
UA = {"User-Agent": "Mozilla/5.0 (compatible; jartic-traffic-signal-cycle-converter)"}


def page_name(target_id: str) -> str:
    """カタログの id（R01_1 / R02）から位置情報ページのファイル名を作る。"""
    body = target_id.lstrip("R")
    parts = body.split("_")
    pref = int(parts[0])
    suffix = f"_{parts[1]}" if len(parts) > 1 else ""
    return f"index10_{pref}{suffix}.html"


def download(name: str, out_dir: Path) -> tuple[str, int]:
    req = urllib.request.Request(f"{BASE_URL}/{name}", headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    (out_dir / name).write_bytes(data)
    return name, len(data)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="work/zip/catalog.json")
    p.add_argument("--out", default="work/html")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()

    entry = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    names = [page_name(t["id"]) for t in entry["targetList"]]
    with ThreadPoolExecutor(args.workers) as ex:
        for name, size in ex.map(lambda n: download(n, out_dir), names):
            print(f"  {name}  {size/1000:.0f} KB", flush=True)
    print(f"完了: {out_dir}  {len(names)}ページ", file=sys.stderr)


if __name__ == "__main__":
    main()
