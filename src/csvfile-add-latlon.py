# -*- coding: utf-8 -*-
"""平均サイクル長に交差点の位置座標を付与し、CSV と GeoJSON を出力する。

結合キーは (情報源コード, 交差点番号)。交差点番号は情報源コードごとの連番なので、
情報源コードを含めないと別県の交差点と衝突する。

GeoJSON は1行1フィーチャの行区切り形式（.geojsonl）で書く。全国・24時間分で
100万件を超えるため、tippecanoe が並列読み込みできる形式にしておく。

出力:
  {out}/signal_cycle.csv       情報源コード,交差点番号,年月,時間帯,平均サイクル長,lon,lat
  {out}/signal_cycle.geojsonl  同内容の行区切りGeoJSON

使い方:
  python3 src/csvfile-add-latlon.py --average work/national_average_cycle.csv \
      --position work/intersection_position.csv --out work
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def load_positions(path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    pos = {}
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            pos[(row["情報源コード"], row["交差点番号"])] = (row["lon"], row["lat"])
    return pos


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--average", default="work/national_average_cycle.csv")
    p.add_argument("--position", default="work/intersection_position.csv")
    p.add_argument("--out", default="work")
    p.add_argument("--report", default="data/join_report.json",
                   help="情報源コード別の結合率レポートの出力先")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    positions = load_positions(Path(args.position))
    print(f"交差点位置: {len(positions):,}件")

    out_csv = out_dir / "signal_cycle.csv"
    out_geojsonl = out_dir / "signal_cycle.geojsonl"

    matched = 0
    missing_keys: set[tuple[str, str]] = set()
    total = 0

    with Path(args.average).open(encoding="utf-8") as fin, \
            out_csv.open("w", newline="", encoding="utf-8") as fcsv, \
            out_geojsonl.open("w", encoding="utf-8") as fgeo:
        reader = csv.DictReader(fin)
        writer = csv.writer(fcsv)
        writer.writerow(["情報源コード", "交差点番号", "年月", "時間帯", "平均サイクル長", "lon", "lat"])
        for row in reader:
            total += 1
            key = (row["情報源コード"], row["交差点番号"])
            lonlat = positions.get(key)
            if lonlat is None:
                missing_keys.add(key)
                continue
            lon, lat = lonlat
            cycle = float(row["平均サイクル長"])
            writer.writerow([row["情報源コード"], row["交差点番号"], row["年月"],
                             row["時間帯"], row["平均サイクル長"], lon, lat])
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {
                    "情報源コード": row["情報源コード"],
                    "交差点番号": row["交差点番号"],
                    "年月": row["年月"],
                    "時間帯": row["時間帯"],
                    "平均サイクル長": cycle,
                },
            }
            fgeo.write(json.dumps(feature, ensure_ascii=False) + "\n")
            matched += 1

    rate = matched / total * 100 if total else 0
    print(f"完了: {out_csv} / {out_geojsonl}", file=sys.stderr)
    print(f"  結合 {matched:,} / {total:,} 行（{rate:.1f}%）", file=sys.stderr)
    if missing_keys:
        sample = sorted(missing_keys)[:10]
        print(f"  位置情報が無い交差点: {len(missing_keys):,}箇所  例: {sample}", file=sys.stderr)

    # 結合率はデータ品質の指標なので、成果物として残して更新のたびに差分を追えるようにする。
    write_report(Path(args.report), Path(args.average), positions, missing_keys, matched, total)


def write_report(path: Path, average_path: Path, positions: dict,
                 missing_keys: set, matched: int, total: int) -> None:
    """情報源コードごとの結合状況をJSONに書き出す。"""
    ctrl_by_code: dict[str, set] = {}
    with average_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ctrl_by_code.setdefault(row["情報源コード"], set()).add(row["交差点番号"])

    missing_by_code: dict[str, int] = {}
    for code, number in missing_keys:
        missing_by_code[code] = missing_by_code.get(code, 0) + 1

    year_months = set()
    codes = []
    for code, numbers in sorted(ctrl_by_code.items()):
        miss = missing_by_code.get(code, 0)
        codes.append({
            "情報源コード": code,
            "制御情報の交差点数": len(numbers),
            "位置情報あり": len(numbers) - miss,
            "位置情報なし": miss,
            "結合率": round((len(numbers) - miss) / len(numbers) * 100, 1) if numbers else 0.0,
        })
    with average_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            year_months.add(row["年月"])

    report = {
        "対象年月": sorted(year_months),
        "制御情報の交差点数": len(ctrl_by_code) and sum(len(v) for v in ctrl_by_code.values()),
        "位置情報が付与された交差点数": sum(len(v) for v in ctrl_by_code.values()) - len(missing_keys),
        "位置情報が無い交差点数": len(missing_keys),
        "行の結合率": round(matched / total * 100, 2) if total else 0.0,
        "情報源コード別": codes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  結合レポート: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
