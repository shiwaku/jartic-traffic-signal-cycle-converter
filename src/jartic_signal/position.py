# -*- coding: utf-8 -*-
"""交差点位置情報のHTMLから、交差点番号と座標を取り出す。

ページ内の <option value="…" lon="…" lat="…">交差点番号</option> が交差点1件に対応する。
value 属性は全国通しの連番で、制御情報の交差点番号ではない。**交差点番号はタグのテキスト**。
（例: 函館のページは value=263 / テキスト=1）

交差点番号は情報源コード（都道府県警察・方面）ごとの連番のため、情報源コードとの組でしか
一意にならない。ページと情報源コードの対応はカタログの id から組み立てるが、北海道5方面は
ページの並びと JARTIC の都市の並びが一致しないため、都道府県ごとに交差点番号の集合が
最もよく一致する組み合わせを選び直す（対応が正しいことをデータで検証してから採用する）。
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from itertools import permutations
from pathlib import Path

from . import catalog
from .fetch import page_name
from .paths import WorkPaths

OPTION_RE = re.compile(r"<option\b([^>]*)>([^<]*)</option>", re.IGNORECASE)
ATTR_RE = re.compile(r"""(\w+)\s*=\s*["']([^"']*)["']""")

# 総当たりは件数の階乗になる。北海道の5方面（120通り）が現状の最大だが、将来コードが
# 増えても破綻しないよう、この数を超えたら貪欲法に切り替える。
MAX_PERMUTATION_CODES = 7


def pref_no(target_id: str) -> int:
    return int(target_id.lstrip("R").split("_")[0])


def parse_options(text: str) -> list:
    """(交差点番号, lon, lat) のリスト。座標のない選択肢（先頭の「－」）は捨てる。"""
    out = []
    for attrs_str, label in OPTION_RE.findall(text):
        attrs = dict(ATTR_RE.findall(attrs_str))
        lon, lat = attrs.get("lon"), attrs.get("lat")
        number = label.strip()
        if lon and lat and number:
            out.append((number, lon, lat))
    return out


def load_control_numbers(path: Path) -> dict:
    """情報源コード → 交差点番号の集合（制御情報側）。"""
    numbers = defaultdict(set)
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            numbers[row["情報源コード"]].add(row["交差点番号"])
    return numbers


def best_assignment(pages: list, codes: list, page_nums: dict, code_nums: dict) -> tuple:
    """ページと情報源コードの対応のうち、交差点番号の一致数が最大の組み合わせを返す。"""
    if len(codes) > MAX_PERMUTATION_CODES:
        return greedy_assignment(pages, codes, page_nums, code_nums)
    best, best_score = None, -1
    for perm in permutations(codes):
        score = sum(len(page_nums[p] & code_nums.get(c, set())) for p, c in zip(pages, perm))
        if score > best_score:
            best, best_score = perm, score
    return best, best_score


def greedy_assignment(pages: list, codes: list, page_nums: dict, code_nums: dict) -> tuple:
    """一致数の大きいペアから順に確定させる（総当たりが現実的でない件数のとき）。"""
    pairs = sorted(
        ((len(page_nums[p] & code_nums.get(c, set())), p, c) for p in pages for c in codes),
        key=lambda x: -x[0])
    assigned: dict = {}
    used_codes: set = set()
    for _score, page, code in pairs:
        if page in assigned or code in used_codes:
            continue
        assigned[page] = code
        used_codes.add(code)
    order = tuple(assigned[p] for p in pages)
    total = sum(len(page_nums[p] & code_nums.get(c, set())) for p, c in zip(pages, order))
    return order, total


def run(work: WorkPaths) -> None:
    entry = catalog.load_entry(work.catalog)
    zip_codes = json.loads(work.source_codes.read_text(encoding="utf-8"))
    code_nums = load_control_numbers(work.average_csv)

    # 都道府県ごとに、ページと情報源コードをまとめる
    groups: dict = defaultdict(lambda: {"pages": [], "codes": []})
    parsed: dict = {}
    warnings: list = []

    for target in entry["targetList"]:
        name = page_name(target["id"])
        path = work.html_dir / name
        if not path.exists():
            warnings.append(f"{name}: HTML未取得")
            continue
        codes = zip_codes.get(catalog.zip_name(target), [])
        if len(codes) != 1:
            warnings.append(f"{name}: 情報源コードが{len(codes)}件（{codes}）")
            continue
        parsed[name] = parse_options(path.read_text(encoding="utf-8", errors="replace"))
        g = groups[pref_no(target["id"])]
        g["pages"].append(name)
        g["codes"].append(codes[0])

    page_nums = {n: {x[0] for x in rows} for n, rows in parsed.items()}

    rows_out: list = []
    fatal: list = []
    total_hit = total_ctrl = 0
    for pref in sorted(groups):
        pages, codes = groups[pref]["pages"], groups[pref]["codes"]
        assign, _score = best_assignment(pages, codes, page_nums, code_nums)
        for name, code in zip(pages, assign):
            hit = len(page_nums[name] & code_nums.get(code, set()))
            ctrl = len(code_nums.get(code, set()))
            total_hit += hit
            total_ctrl += ctrl
            mark = "" if hit == ctrl else f"  ←制御側{ctrl}件中{hit}件のみ一致"
            print(f"  {name}  情報源コード={code}  位置{len(page_nums[name]):,}件{mark}", flush=True)
            if hit == 0 and ctrl:
                warnings.append(f"{name}↔{code}: 交差点番号が1件も一致しない")
                fatal.append(f"{name}↔{code}")
            for number, lon, lat in parsed[name]:
                rows_out.append((code, number, lon, lat))

    with work.position_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["情報源コード", "交差点番号", "lon", "lat"])
        w.writerows(rows_out)

    rate = total_hit / total_ctrl * 100 if total_ctrl else 0
    print(f"完了: {work.position_csv}  {len(rows_out):,}件", file=sys.stderr)
    print(f"  制御情報の交差点 {total_ctrl:,}箇所のうち {total_hit:,}箇所に位置あり（{rate:.1f}%）",
          file=sys.stderr)
    for w_ in warnings:
        print(f"  警告: {w_}", file=sys.stderr)

    # 1件も一致しないのは、位置情報ページの構造が変わったなどの異常。座標が付かないまま
    # 先に進むと結合率だけが静かに落ちるため、ここで止める。
    if fatal:
        raise SystemExit("交差点番号が一致しないページがあるため中断します: " + ", ".join(fatal))
