# -*- coding: utf-8 -*-
"""JARTIC のカタログJSONの解決。

配布URLは月次で変わる（.../opendata/{更新日時}/typeC_{都市名}_{年_月}.zip）ため、
更新日時や対象年月をスクリプトに埋め込まず、毎回ここから解決する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import http

CATALOG_URL = "https://www.jartic.or.jp/d/opendata/opendata.json"
BASE_URL = "https://www.jartic.or.jp/d/opendata"
POSITION_URL = "https://www.tmt.or.jp/research/index10.html"


def fetch_entry(url: str = CATALOG_URL) -> dict:
    """カタログJSONから交差点制御情報（typeC）のエントリを返す。"""
    catalog = json.loads(http.get(url, timeout=60, label="catalog.json"))
    for entry in catalog:
        if entry.get("type") == "typeC":
            return entry
    raise SystemExit("カタログに typeC（交差点制御情報）が見つかりません")


def load_entry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_month(target_month: str) -> str:
    """'2026年06月' → '202606'"""
    m = re.match(r"(\d{4})年(\d{2})月", target_month or "")
    if not m:
        raise SystemExit(f"対象年月を解釈できません: {target_month!r}")
    return m.group(1) + m.group(2)


def normalize_day(release_day: str) -> str:
    """'2026年08月01日' → '2026-08-01'"""
    m = re.match(r"(\d{4})年(\d{2})月(\d{2})日", release_day or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else (release_day or "")


def display_month(year_month: str) -> str:
    """'202606' → '2026年6月'（表示用。ゼロ埋めしない）"""
    return f"{year_month[:4]}年{int(year_month[4:6])}月"


def zip_url(target: dict) -> str:
    return BASE_URL + target["link"]


def zip_name(target: dict) -> str:
    return target["link"].split("/")[-1]
