# -*- coding: utf-8 -*-
"""交差点制御情報（zip）から、交差点ごと・時間帯ごとの平均サイクル長を算出する。

zip を展開せずストリーム処理する。制御CSVは1都市で100MB超あり、全国分を展開すると
数GBになるため、読みながら (情報源コード, 交差点番号, 年月, 時間帯) 単位で
合計と件数だけを持ち回る。

制御CSVの列: 時刻, 情報源コード, 交差点番号, サイクル長, スプリット＃1〜6, リンクバージョン
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

from .paths import WorkPaths

# 制御CSVかどうかはファイル名の「制御」で判定する（同じ zip に「定義」CSVも入っている）。
CONTROL_RE = re.compile(r"制御")


def zip_member_name(info: zipfile.ZipInfo) -> str:
    """zip内のファイル名を復元する（cp932 で格納されている場合がある）。"""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp932")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def accumulate(rows: Iterable[list], totals: dict, codes: set) -> int:
    """制御CSVの行を集計に加え、採用した行数を返す。

    サイクル長が空・非数値の行は捨てる。時刻は "YYYY/MM/DD HH:MM" 固定長で、
    年月と時だけを使う。
    """
    used = 0
    for row in rows:
        if len(row) < 4:
            continue
        timestamp, info_code, intersection, cycle = row[:4]
        if not cycle:
            continue
        try:
            cycle_len = int(cycle)
        except ValueError:
            continue
        key = (info_code, intersection, timestamp[0:4] + timestamp[5:7], timestamp[11:13])
        agg = totals[key]
        agg[0] += cycle_len
        agg[1] += 1
        used += 1
        codes.add(info_code)
    return used


def read_control_rows(path: Path) -> Iterator[list]:
    """zip 内の制御CSVの行を、ヘッダーを除いて順に返す。"""
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir() or not CONTROL_RE.search(zip_member_name(info)):
                continue
            with z.open(info) as f:
                reader = csv.reader(io.TextIOWrapper(f, encoding="cp932", errors="replace"))
                next(reader, None)  # ヘッダー行
                for row in reader:
                    yield row


def aggregate(zip_paths: list) -> tuple:
    """zip 群を集計して (totals, zip名→情報源コード) を返す。"""
    totals: dict = defaultdict(lambda: [0, 0])
    per_zip_codes: dict = {}
    for i, path in enumerate(zip_paths, 1):
        codes: set = set()
        rows = accumulate(read_control_rows(path), totals, codes)
        per_zip_codes[path.name] = sorted(codes)
        print(f"[{i}/{len(zip_paths)}] {path.name}  {rows:,}行  情報源コード={sorted(codes)}",
              flush=True)
    return totals, per_zip_codes


def write_average_csv(path: Path, totals: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["情報源コード", "交差点番号", "年月", "時間帯", "平均サイクル長"])
        for (info_code, intersection, year_month, hour), (total, count) in sorted(totals.items()):
            w.writerow([info_code, intersection, year_month, f"{hour}:00", f"{total / count:.2f}"])


def run(work: WorkPaths) -> None:
    work.mkdirs()
    zips = sorted(work.zip_dir.glob("typeC_*.zip"))
    if not zips:
        raise SystemExit(f"{work.zip_dir} に typeC_*.zip がありません")

    totals, per_zip_codes = aggregate(zips)
    write_average_csv(work.average_csv, totals)
    work.source_codes.write_text(json.dumps(per_zip_codes, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    intersections = {(k[0], k[1]) for k in totals}
    print(f"完了: {work.average_csv}  {len(totals):,}行 / 交差点 {len(intersections):,}箇所",
          file=sys.stderr)
