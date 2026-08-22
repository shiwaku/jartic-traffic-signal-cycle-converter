# -*- coding: utf-8 -*-
"""品質ゲート。

人のレビューを挟まずに公開するため、ここが唯一の防波堤になる。判定は副作用を持たない
純関数にして、テストで固定入力から確かめられるようにしている。

判定は2種類ある。

* 前回比 … 静かに劣化していないか（対象年月・交差点数・結合率・中央値・タイルサイズ）
* 絶対値 … そもそも値として妥当か（値域・時間帯の網羅・座標の範囲・結合できないコード）

前回比は初回（前回データが無いとき）には効かないので、絶対値の判定を併せて置いている。
"""
from __future__ import annotations


class Thresholds:
    def __init__(
        self,
        max_intersection_drop: float = 5.0,   # 交差点数の前回比（%）
        max_join_rate_drop: float = 2.0,      # 行の結合率の前回比（ポイント）
        max_median_shift: float = 10.0,       # サイクル長中央値の前回比（秒・増減とも）
        max_out_of_range_ratio: float = 0.1,  # 値域外レコードの割合（%）
        max_incomplete_ratio: float = 1.0,    # 24時間帯が揃わない交差点の割合（%）
        max_tile_size_shift: float = 50.0,    # PMTiles サイズの前回比（%・増減とも）
    ) -> None:
        self.max_intersection_drop = max_intersection_drop
        self.max_join_rate_drop = max_join_rate_drop
        self.max_median_shift = max_median_shift
        self.max_out_of_range_ratio = max_out_of_range_ratio
        self.max_incomplete_ratio = max_incomplete_ratio
        self.max_tile_size_shift = max_tile_size_shift


def check(new: dict, old: dict, report: dict, th: Thresholds | None = None) -> list:
    """公開してよいかを判定し、違反の一覧を返す（空なら通過）。"""
    th = th or Thresholds()
    v: list = []

    _check_absolute(new, report, th, v)
    if old:
        _check_against_previous(new, old, th, v)
    return v


def _check_absolute(new: dict, report: dict, th: Thresholds, v: list) -> None:
    records = new.get("結合レコード数") or 0
    out_of_range = new.get("値域外レコード数") or 0
    if records and out_of_range:
        ratio = out_of_range / records * 100
        if ratio > th.max_out_of_range_ratio:
            v.append(f"サイクル長が妥当な範囲を外れるレコードが {out_of_range:,}件"
                     f"（{ratio:.2f}%、許容 {th.max_out_of_range_ratio}%）")

    intersections = new.get("位置情報が付与された交差点数") or 0
    incomplete = new.get("時間帯が欠けている交差点数") or 0
    if intersections and incomplete:
        ratio = incomplete / intersections * 100
        if ratio > th.max_incomplete_ratio:
            v.append(f"24時間帯が揃わない交差点が {incomplete:,}箇所"
                     f"（{ratio:.2f}%、許容 {th.max_incomplete_ratio}%）")

    out_of_bbox = new.get("範囲外の座標数") or 0
    if out_of_bbox:
        v.append(f"日本の範囲外にある座標が {out_of_bbox:,}件")

    zero = [c["情報源コード"] for c in report.get("情報源コード別", [])
            if c["制御情報の交差点数"] and c["位置情報あり"] == 0]
    if zero:
        v.append(f"位置情報が1件も結合できない情報源コード: {', '.join(zero)}")


def _check_against_previous(new: dict, old: dict, th: Thresholds, v: list) -> None:
    if new["対象年月"] <= old.get("対象年月", ""):
        v.append(f"対象年月が進んでいない（今回 {new['対象年月']} / 前回 {old.get('対象年月')}）")

    old_n = old.get("交差点数") or 0
    if old_n:
        drop = (old_n - new["交差点数"]) / old_n * 100
        if drop > th.max_intersection_drop:
            v.append(f"交差点数が前回比 -{drop:.1f}%（{old_n:,} → {new['交差点数']:,}、"
                     f"許容 -{th.max_intersection_drop}%）")

    old_rate = old.get("行の結合率")
    if old_rate is not None:
        drop = old_rate - new["行の結合率"]
        if drop > th.max_join_rate_drop:
            v.append(f"行の結合率が前回比 -{drop:.2f}pt（{old_rate}% → {new['行の結合率']}%、"
                     f"許容 -{th.max_join_rate_drop}pt）")

    old_median = old.get("サイクル長中央値")
    new_median = new.get("サイクル長中央値")
    if old_median and new_median:
        shift = new_median - old_median
        if abs(shift) > th.max_median_shift:
            v.append(f"サイクル長の中央値が前回比 {shift:+.0f}秒"
                     f"（{old_median}秒 → {new_median}秒、許容 ±{th.max_median_shift:.0f}秒）")

    old_size = old.get("PMTilesバイト数")
    new_size = new.get("PMTilesバイト数")
    if old_size and new_size:
        shift = (new_size - old_size) / old_size * 100
        if abs(shift) > th.max_tile_size_shift:
            v.append(f"PMTiles のサイズが前回比 {shift:+.0f}%"
                     f"（{old_size / 1e6:.1f}MB → {new_size / 1e6:.1f}MB、"
                     f"許容 ±{th.max_tile_size_shift:.0f}%）")


def source_code_diff(new_report: dict, old_report: dict, top: int = 5) -> list:
    """情報源コード別の結合率の変化が大きい順。ゲート通過後の記録用。"""
    old_by = {c["情報源コード"]: c for c in old_report.get("情報源コード別", [])}
    rows = []
    for c in new_report.get("情報源コード別", []):
        o = old_by.get(c["情報源コード"])
        if not o:
            continue
        delta = c["結合率"] - o["結合率"]
        if abs(delta) >= 0.05:
            rows.append((c["情報源コード"], o["結合率"], c["結合率"], delta))
    rows.sort(key=lambda r: abs(r[3]), reverse=True)
    return rows[:top]
