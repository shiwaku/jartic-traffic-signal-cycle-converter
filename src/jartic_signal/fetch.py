# -*- coding: utf-8 -*-
"""交差点制御情報（zip）と交差点位置情報（HTML）の取得。"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import catalog, http
from .paths import WorkPaths

POSITION_BASE_URL = "https://www.tmt.or.jp/research"
# zip は1ファイル最大70MB。応答が止まったら打ち切って取り直す。
ZIP_TIMEOUT = 180
HTML_TIMEOUT = 60


def download_zips(work: WorkPaths, workers: int = 4, entry: dict | None = None) -> dict:
    """カタログを解決して typeC の zip を一括取得し、採用したエントリを返す。"""
    work.mkdirs()
    entry = entry or catalog.fetch_entry()
    print(f"交差点制御情報 対象={entry['targetMonth']} 公開={entry['releaseDay']} "
          f"{len(entry['targetList'])}ファイル")
    work.catalog.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

    def one(target: dict) -> tuple:
        name = catalog.zip_name(target)
        size = http.download(catalog.zip_url(target), work.zip_dir / name, timeout=ZIP_TIMEOUT)
        return name, size

    total = 0
    with ThreadPoolExecutor(workers) as ex:
        for name, size in ex.map(one, entry["targetList"]):
            total += size
            print(f"  {name}  {'スキップ（取得済）' if size == 0 else f'{size / 1e6:.1f} MB'}",
                  flush=True)
    print(f"完了: {work.zip_dir}  新規取得 {total / 1e6:.0f} MB", file=sys.stderr)
    return entry


def page_name(target_id: str) -> str:
    """カタログの id（R01_1 / R02）から位置情報ページのファイル名を作る。

    ページは都道府県ごと（北海道のみ方面別に5ページ）に分かれており、カタログの
    targetList と1対1で対応する。
    """
    parts = target_id.lstrip("R").split("_")
    suffix = f"_{parts[1]}" if len(parts) > 1 else ""
    return f"index10_{int(parts[0])}{suffix}.html"


def download_pages(work: WorkPaths, workers: int = 4) -> int:
    """交差点位置情報のHTMLを一括取得する。"""
    work.mkdirs()
    entry = catalog.load_entry(work.catalog)
    names = [page_name(t["id"]) for t in entry["targetList"]]

    def one(name: str) -> tuple:
        data = http.get(f"{POSITION_BASE_URL}/{name}", timeout=HTML_TIMEOUT, label=name)
        (work.html_dir / name).write_bytes(data)
        return name, len(data)

    with ThreadPoolExecutor(workers) as ex:
        for name, size in ex.map(one, names):
            print(f"  {name}  {size / 1000:.0f} KB", flush=True)
    print(f"完了: {work.html_dir}  {len(names)}ページ", file=sys.stderr)
    return len(names)
