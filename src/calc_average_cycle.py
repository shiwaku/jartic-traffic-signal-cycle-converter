# -*- coding: utf-8 -*-
"""交差点制御情報（zip）から、交差点ごと・時間帯ごとの平均サイクル長を算出する。

zip を展開せずストリーム処理する。制御CSVは1都市で100MB超あり、全国分を展開すると
数GBになるため、読みながら (情報源コード, 交差点番号, 年月, 時間帯) 単位で
合計と件数だけを持ち回る。

制御CSVの列: 時刻, 情報源コード, 交差点番号, サイクル長, スプリット＃1〜6, リンクバージョン

出力:
  {out}/national_average_cycle.csv  情報源コード,交差点番号,年月,時間帯,平均サイクル長
  {out}/source_codes.json           zip名 → 情報源コード（交差点位置情報の突合に使う）

使い方:
  python3 src/calc_average_cycle.py --zip-dir work/zip --out work
"""
import argparse
import csv
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

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


def process_zip(path: Path, totals: dict, codes: set) -> int:
    """1つの zip 内の制御CSVを集計に加え、読んだ行数を返す。"""
    rows = 0
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir() or not CONTROL_RE.search(zip_member_name(info)):
                continue
            with z.open(info) as f:
                reader = csv.reader(io.TextIOWrapper(f, encoding="cp932", errors="replace"))
                next(reader, None)  # ヘッダー行
                for row in reader:
                    if len(row) < 4:
                        continue
                    timestamp, info_code, intersection, cycle = row[:4]
                    if not cycle:
                        continue
                    try:
                        cycle_len = int(cycle)
                    except ValueError:
                        continue
                    # 時刻は "YYYY/MM/DD HH:MM"。年月と時のみ使う。
                    year_month = timestamp[0:4] + timestamp[5:7]
                    hour = timestamp[11:13]
                    key = (info_code, intersection, year_month, hour)
                    agg = totals[key]
                    agg[0] += cycle_len
                    agg[1] += 1
                    rows += 1
                    codes.add(info_code)
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip-dir", default="work/zip")
    p.add_argument("--out", default="work")
    args = p.parse_args()

    zip_dir = Path(args.zip_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    zips = sorted(zip_dir.glob("typeC_*.zip"))
    if not zips:
        raise SystemExit(f"{zip_dir} に typeC_*.zip がありません")

    totals: dict[tuple, list] = defaultdict(lambda: [0, 0])
    per_zip_codes: dict[str, list[str]] = {}

    for i, path in enumerate(zips, 1):
        codes: set[str] = set()
        rows = process_zip(path, totals, codes)
        per_zip_codes[path.name] = sorted(codes)
        print(f"[{i}/{len(zips)}] {path.name}  {rows:,}行  情報源コード={sorted(codes)}",
              flush=True)

    out_csv = out_dir / "national_average_cycle.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["情報源コード", "交差点番号", "年月", "時間帯", "平均サイクル長"])
        for (info_code, intersection, year_month, hour), (total, count) in sorted(totals.items()):
            w.writerow([info_code, intersection, year_month, f"{hour}:00",
                        f"{total / count:.2f}"])

    (out_dir / "source_codes.json").write_text(
        json.dumps(per_zip_codes, ensure_ascii=False, indent=2), encoding="utf-8")

    intersections = {(k[0], k[1]) for k in totals}
    print(f"完了: {out_csv}  {len(totals):,}行 / 交差点 {len(intersections):,}箇所",
          file=sys.stderr)


if __name__ == "__main__":
    main()
