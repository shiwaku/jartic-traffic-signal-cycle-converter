# -*- coding: utf-8 -*-
"""平均サイクル長に交差点の位置座標を付与し、CSV と GeoJSON を出力する。

結合キーは (情報源コード, 交差点番号)。交差点番号は情報源コードごとの連番なので、
情報源コードを含めないと別県の交差点と衝突する。

GeoJSON は**1交差点1フィーチャ**で書き、24時間帯の値を属性 c0〜c23 に持たせる。
時間帯ごとに別フィーチャにすると同じ座標が24回並び、tippecanoe が低ズームでそれを
「密な重複」と見て 23/24 を落とす（実測: ズーム6以下では 00:00 のときしか点が残らない）。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from .paths import WorkPaths

# 品質判定に使うしきい値。サイクル長は 30 秒を切ることも 400 秒を超えることも実運用では無い。
VALID_CYCLE = (30, 400)
# 日本の領域。座標の取り違えや度分秒の混入をここで捕まえる。
JAPAN_BBOX = (122.0, 20.0, 154.0, 46.0)  # lon_min, lat_min, lon_max, lat_max


class JoinResult:
    def __init__(self) -> None:
        # (情報源コード, 交差点番号) → {時: 秒}
        self.by_intersection: dict = {}
        # (情報源コード, 交差点番号) → (lon, lat)
        self.coords: dict = {}
        self.missing_keys: set = set()
        self.matched = 0
        self.total = 0


def load_positions(path: Path) -> dict:
    pos = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pos[(row["情報源コード"], row["交差点番号"])] = (row["lon"], row["lat"])
    return pos


def join(average_csv: Path, positions: dict, joined_csv: Path) -> JoinResult:
    """平均サイクル長に座標を結合しながら、交差点ごとに24時間分をまとめる。"""
    r = JoinResult()
    with average_csv.open(encoding="utf-8") as fin, \
            joined_csv.open("w", newline="", encoding="utf-8") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["情報源コード", "交差点番号", "年月", "時間帯", "平均サイクル長", "lon", "lat"])
        for row in csv.DictReader(fin):
            r.total += 1
            key = (row["情報源コード"], row["交差点番号"])
            lonlat = positions.get(key)
            if lonlat is None:
                r.missing_keys.add(key)
                continue
            lon, lat = lonlat
            writer.writerow([row["情報源コード"], row["交差点番号"], row["年月"],
                             row["時間帯"], row["平均サイクル長"], lon, lat])
            # 1か月平均に 0.1 秒の意味は無く、整数のほうが MVT の varint に乗る。
            hour = int(row["時間帯"][:2])
            r.by_intersection.setdefault(key, {})[hour] = round(float(row["平均サイクル長"]))
            r.coords[key] = (float(lon), float(lat))
            r.matched += 1
    return r


def write_geojsonl(path: Path, r: JoinResult) -> None:
    """1交差点1フィーチャの行区切りGeoJSONを書く。欠測の時間帯はキーごと省く。

    属性名は式から扱いやすいよう ASCII に短縮する（src / no / c0〜c23）。年月は全レコードで
    同一なのでフィーチャには持たせず、dataset.json 側に持つ。最小・最大・平均といった
    派生値は 24 個の値から即座に計算できるためタイルには入れない（5つ足すと 0.7MB 増える）。
    """
    with path.open("w", encoding="utf-8") as f:
        for key, hours in r.by_intersection.items():
            lon, lat = r.coords[key]
            props: dict = {"src": key[0], "no": key[1]}
            for hour in sorted(hours):
                props[f"c{hour}"] = hours[hour]
            f.write(json.dumps({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }, ensure_ascii=False) + "\n")


def hourly_stats(r: JoinResult) -> list:
    """時間帯ごとの全国分布（四分位）。

    ビューワのタイムバーが「その時間帯は全国的に長いのか」を示すために使う。全国値なので
    地図の表示範囲に依らず、毎回タイルから数え直すよりここで一度求めるほうが素直。
    品質ゲートの「中央値の前回比」も同じ値を見る。
    """
    by_hour: dict = {}
    for hours in r.by_intersection.values():
        for hour, value in hours.items():
            by_hour.setdefault(hour, []).append(value)

    def q(values: list, ratio: float) -> int:
        return values[min(len(values) - 1, int(len(values) * ratio))]

    stats = []
    for hour in range(24):
        values = sorted(by_hour.get(hour, []))
        if not values:
            stats.append({"時間帯": hour, "件数": 0})
            continue
        stats.append({"時間帯": hour, "件数": len(values),
                      "p25": q(values, 0.25), "中央値": q(values, 0.5), "p75": q(values, 0.75)})
    return stats


def quality(r: JoinResult) -> dict:
    """値そのものの妥当性。結合率だけでは「値がおかしい」データが素通りするため見る。"""
    values = sorted(v for hours in r.by_intersection.values() for v in hours.values())
    lo, hi = VALID_CYCLE
    out_of_range = sum(1 for v in values if v < lo or v > hi)
    incomplete = sum(1 for hours in r.by_intersection.values() if len(hours) < 24)
    x0, y0, x1, y1 = JAPAN_BBOX
    out_of_bbox = sum(1 for lon, lat in r.coords.values()
                      if not (x0 <= lon <= x1 and y0 <= lat <= y1))
    return {
        "サイクル長中央値": values[len(values) // 2] if values else 0,
        "値域外レコード数": out_of_range,
        "時間帯が欠けている交差点数": incomplete,
        "範囲外の座標数": out_of_bbox,
    }


def build_report(average_csv: Path, r: JoinResult) -> dict:
    """情報源コードごとの結合状況。データ品質の指標として成果物に残す。"""
    ctrl_by_code: dict = {}
    year_months = set()
    with average_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ctrl_by_code.setdefault(row["情報源コード"], set()).add(row["交差点番号"])
            year_months.add(row["年月"])

    missing_by_code: dict = {}
    for code, _number in r.missing_keys:
        missing_by_code[code] = missing_by_code.get(code, 0) + 1

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

    total_intersections = sum(len(v) for v in ctrl_by_code.values())
    return {
        "対象年月": sorted(year_months),
        "制御情報の交差点数": total_intersections,
        "位置情報が付与された交差点数": total_intersections - len(r.missing_keys),
        "位置情報が無い交差点数": len(r.missing_keys),
        "行の結合率": round(r.matched / r.total * 100, 2) if r.total else 0.0,
        "情報源コード別": codes,
    }


def run(work: WorkPaths) -> dict:
    work.mkdirs()
    positions = load_positions(work.position_csv)
    print(f"交差点位置: {len(positions):,}件")

    r = join(work.average_csv, positions, work.joined_csv)
    write_geojsonl(work.geojsonl, r)

    report = build_report(work.average_csv, r)
    work.join_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    work.hourly_stats.write_text(json.dumps(hourly_stats(r), ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")

    rate = r.matched / r.total * 100 if r.total else 0
    print(f"完了: {work.joined_csv} / {work.geojsonl}", file=sys.stderr)
    print(f"  結合 {r.matched:,} / {r.total:,} 行（{rate:.1f}%）"
          f" → {len(r.by_intersection):,} フィーチャ", file=sys.stderr)
    if r.missing_keys:
        sample = sorted(r.missing_keys)[:10]
        print(f"  位置情報が無い交差点: {len(r.missing_keys):,}箇所  例: {sample}", file=sys.stderr)
    print(f"  結合レポート: {work.join_report}", file=sys.stderr)
    print(f"  時間帯別統計: {work.hourly_stats}", file=sys.stderr)

    summary = {"report": report, "quality": quality(r), "features": len(r.by_intersection)}
    work.join_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    return summary
