# -*- coding: utf-8 -*-
"""平均サイクル長に交差点の位置座標を付与し、CSV と GeoJSON を出力する。

結合キーは (情報源コード, 交差点番号)。交差点番号は情報源コードごとの連番なので、
情報源コードを含めないと別県の交差点と衝突する。

GeoJSON は**1交差点1フィーチャ**で書き、24時間帯の値を属性 c0〜c23 に持たせる。
時間帯ごとに別フィーチャにすると同じ座標が24回並び、tippecanoe が低ズームでそれを
「密な重複」と見て 23/24 を落とす（実測: ズーム6以下では 00:00 のときしか点が残らない）。
1フィーチャにまとめると全点が全ズームに残り、タイルも 13.8MB → 5.0MB に縮む。

属性名は式から扱いやすいよう ASCII に短縮する（src / no / c0〜c23）。年月は全レコードで
同一なのでフィーチャには持たせず、dataset.json 側に持つ。1か月平均に 0.1 秒の意味は
無いので整数秒に丸める。最小・最大・平均といった派生値は 24 個の値から即座に計算できる
ため、タイルには入れない（5つ足すとタイルが 0.7MB 増える）。

出力:
  {out}/signal_cycle.csv       情報源コード,交差点番号,年月,時間帯,平均サイクル長,lon,lat
  {out}/signal_cycle.geojsonl  1交差点1フィーチャの行区切りGeoJSON（src,no,c0〜c23）

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
    # 交差点ごとに24時間分をまとめる。全国 10,543 箇所 × 24 値なので素直に持てる。
    by_intersection: dict[tuple[str, str], dict[int, int]] = {}

    with Path(args.average).open(encoding="utf-8") as fin, \
            out_csv.open("w", newline="", encoding="utf-8") as fcsv:
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
            writer.writerow([row["情報源コード"], row["交差点番号"], row["年月"],
                             row["時間帯"], row["平均サイクル長"], lon, lat])
            hour = int(row["時間帯"][:2])
            by_intersection.setdefault(key, {})[hour] = round(float(row["平均サイクル長"]))
            matched += 1

    write_geojsonl(out_geojsonl, by_intersection, positions)
    write_hourly_stats(out_dir / "hourly_stats.json", by_intersection)

    rate = matched / total * 100 if total else 0
    print(f"完了: {out_csv} / {out_geojsonl}", file=sys.stderr)
    print(f"  結合 {matched:,} / {total:,} 行（{rate:.1f}%）"
          f" → {len(by_intersection):,} フィーチャ", file=sys.stderr)
    if missing_keys:
        sample = sorted(missing_keys)[:10]
        print(f"  位置情報が無い交差点: {len(missing_keys):,}箇所  例: {sample}", file=sys.stderr)

    # 結合率はデータ品質の指標なので、成果物として残して更新のたびに差分を追えるようにする。
    write_report(Path(args.report), Path(args.average), positions, missing_keys, matched, total)


def write_geojsonl(path: Path, by_intersection: dict, positions: dict) -> None:
    """1交差点1フィーチャの行区切りGeoJSONを書く。欠測の時間帯はキーごと省く。"""
    with path.open("w", encoding="utf-8") as f:
        for (code, number), hours in by_intersection.items():
            lon, lat = positions[(code, number)]
            props: dict[str, object] = {"src": code, "no": number}
            for hour in sorted(hours):
                props[f"c{hour}"] = hours[hour]
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": props,
            }
            f.write(json.dumps(feature, ensure_ascii=False) + "\n")


def write_hourly_stats(path: Path, by_intersection: dict) -> None:
    """時間帯ごとの全国分布（四分位）を書き出す。

    ビューワのタイムバーが「その時間帯は全国的に長いのか」を示すために使う。全国値なので
    地図の表示範囲に依らず、毎回タイルから数え直すよりここで一度求めるほうが素直。
    品質ゲートの「中央値の前回比」もこの値を見る。
    """
    by_hour: dict[int, list[int]] = {}
    for hours in by_intersection.values():
        for hour, value in hours.items():
            by_hour.setdefault(hour, []).append(value)

    def quantile(sorted_values: list[int], q: float) -> int:
        return sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * q))]

    stats = []
    for hour in range(24):
        values = sorted(by_hour.get(hour, []))
        if not values:
            stats.append({"時間帯": hour, "件数": 0})
            continue
        stats.append({
            "時間帯": hour,
            "件数": len(values),
            "p25": quantile(values, 0.25),
            "中央値": quantile(values, 0.5),
            "p75": quantile(values, 0.75),
        })

    path.write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  時間帯別統計: {path}", file=sys.stderr)


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
