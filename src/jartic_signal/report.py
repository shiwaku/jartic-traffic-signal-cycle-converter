# -*- coding: utf-8 -*-
"""dataset.json の組み立てと、README・Release ノートの生成。

対象年月や交差点数を人が転記すると、データだけ更新して文言が古いまま残る。
dataset.json を単一の情報源にして、README のこの節もビューワの表示もそこから生成する。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import catalog
from .paths import DataPaths, WorkPaths

JST = timezone(timedelta(hours=9))

# 情報源コードは都道府県警察（北海道のみ方面）ごとに振られる。表示用の名前を引くために使う。
PREFS = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木", "群馬",
    "埼玉", "千葉", "東京", "神奈川", "新潟", "富山", "石川", "福井", "山梨", "長野",
    "岐阜", "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山",
    "鳥取", "島根", "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知", "福岡",
    "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄",
]
HOKKAIDO_AREAS = {"sapporo": "札幌", "hakodate": "函館", "asahikawa": "旭川",
                  "kushiro": "釧路", "kitami": "北見"}

LOW_JOIN_THRESHOLD = 95.0  # この結合率を下回る情報源コードを README に列挙する


def count_rows(path: Path) -> int:
    """ヘッダーを除いた行数。"""
    with path.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_dataset(year_month: str, release_day: str, report: dict, quality: dict,
                  total_rows: int, joined_rows: int, pmtiles: Path) -> dict:
    """公開するデータセットの要約。品質ゲートはこの前回分と今回分を比べる。"""
    return {
        "対象年月": year_month,
        "対象年月_表示": catalog.display_month(year_month),
        "公開日": release_day,
        "交差点数": report["制御情報の交差点数"],
        "位置情報が付与された交差点数": report["位置情報が付与された交差点数"],
        "レコード数": total_rows,
        "結合レコード数": joined_rows,
        "行の結合率": report["行の結合率"],
        "サイクル長中央値": quality["サイクル長中央値"],
        "値域外レコード数": quality["値域外レコード数"],
        "時間帯が欠けている交差点数": quality["時間帯が欠けている交差点数"],
        "範囲外の座標数": quality["範囲外の座標数"],
        "PMTilesバイト数": pmtiles.stat().st_size if pmtiles.exists() else 0,
        "生成日時": datetime.now(JST).isoformat(timespec="seconds"),
        "出典": {
            "交差点制御情報": catalog.CATALOG_URL,
            "交差点位置情報": catalog.POSITION_URL,
        },
    }


# ---- Release ノートとコミットメッセージ ----

def write_texts(work: WorkPaths, ds: dict, diff: list) -> None:
    """YAML の中に整形処理を持ち込まずに済み、ローカル実行でも同じ文面を確認できる。"""
    lines = [
        f"対象年月 {ds['対象年月_表示']}（JARTIC公開 {ds['公開日']}）",
        f"交差点 {ds['交差点数']:,}箇所（うち座標付与 {ds['位置情報が付与された交差点数']:,}）",
        f"{ds['レコード数']:,}レコード / 行の結合率 {ds['行の結合率']}%",
        f"サイクル長の中央値 {ds['サイクル長中央値']}秒 / PMTiles {ds['PMTilesバイト数'] / 1e6:.1f}MB",
    ]
    if diff:
        lines += ["", "情報源コード別の結合率の変化:"]
        lines += [f"- {code}: {before}% → {after}%（{delta:+.1f}pt）"
                  for code, before, after, delta in diff]
    work.release_notes.write_text("\n".join(lines) + "\n", encoding="utf-8")

    commit = [f"データを{ds['対象年月']}分に更新", "",
              f"交差点 {ds['交差点数']:,}箇所 / {ds['レコード数']:,}レコード / "
              f"結合率 {ds['行の結合率']}%",
              f"PMTiles は Release data-{ds['対象年月']} に添付。生zipは退避済み。"]
    work.commit_message.write_text("\n".join(commit) + "\n", encoding="utf-8")


# ---- README ----

def build_code_names(catalog_path: Path, codes_path: Path) -> dict:
    """情報源コード → 表示名（例: 3001 → 北海道（札幌）、301C → 三重）。

    zip 名（typeC_{都市}_{年}_{月}.zip）とカタログの id を突き合わせて求める。zip の中に
    どのコードが入っていたかは source_codes.json が持っているので、推測は入らない。
    並び順から推測してはいけない（実測で 3010=埼玉 / 3011=千葉 であり、並び順とは違う）。
    """
    if not (catalog_path.exists() and codes_path.exists()):
        return {}
    entry = json.loads(catalog_path.read_text(encoding="utf-8"))
    zip_codes = json.loads(codes_path.read_text(encoding="utf-8"))
    names = {}
    for target in entry.get("targetList", []):
        filename = catalog.zip_name(target)
        codes = zip_codes.get(filename, [])
        if len(codes) != 1:
            continue
        pref = int(target["id"].lstrip("R").split("_")[0])
        name = PREFS[pref - 1] if 1 <= pref <= len(PREFS) else target["id"]
        city = filename.split("_")[1] if "_" in filename else ""
        if pref == 1 and city in HOKKAIDO_AREAS:
            name = f"{name}（{HOKKAIDO_AREAS[city]}）"
        names[codes[0]] = name
    return names


def dataset_table(ds: dict) -> str:
    return "\n".join([
        "| 項目 | 内容 |",
        "|---|---|",
        f"| 対象年月 | {ds['対象年月_表示']} |",
        f"| 公開日 | {ds['公開日']}（JARTIC） |",
        f"| 交差点数 | {ds['交差点数']:,}箇所（うち座標付与 {ds['位置情報が付与された交差点数']:,}） |",
        f"| レコード数 | {ds['レコード数']:,}件（交差点 × 24時間帯） |",
        f"| 地図に載るレコード数 | {ds['結合レコード数']:,}件（座標を付与できた分） |",
        f"| 結合率 | {ds['行の結合率']}%（[data/join_report.json](data/join_report.json) "
        "に情報源コード別の内訳） |",
    ])


def low_join_table(ds: dict, report: dict, names: dict) -> str:
    low = [c for c in report.get("情報源コード別", []) if c["結合率"] < LOW_JOIN_THRESHOLD]
    low.sort(key=lambda c: c["結合率"])
    if not low:
        return f"{ds['対象年月_表示']}時点で、結合率が{LOW_JOIN_THRESHOLD:.0f}%を下回る情報源コードはありません。"
    lines = [f"{ds['対象年月_表示']}時点で結合率が低い情報源コード:", "",
             "| 情報源コード | 都道府県 | 制御情報 | 位置情報あり | 結合率 |", "|---|---|---|---|---|"]
    for c in low:
        lines.append(f"| {c['情報源コード']} | {names.get(c['情報源コード'], '—')} | "
                     f"{c['制御情報の交差点数']:,} | {c['位置情報あり']:,} | {c['結合率']}% |")
    return "\n".join(lines)


def replace_block(text: str, key: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {key}:begin -->\n).*?(\n<!-- {key}:end -->)", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"README に <!-- {key}:begin --> … <!-- {key}:end --> がありません")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def update_readme(readme: Path, data: DataPaths, work: WorkPaths) -> None:
    ds = json.loads(data.dataset.read_text(encoding="utf-8"))
    report = json.loads(data.join_report.read_text(encoding="utf-8"))

    names = build_code_names(work.catalog, work.source_codes)
    if names:
        data.mkdirs()
        data.source_names.write_text(json.dumps(names, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    elif data.source_names.exists():
        names = json.loads(data.source_names.read_text(encoding="utf-8"))
        print(f"注意: zip が無いため {data.source_names} の対応表を使います", file=sys.stderr)
    else:
        print("注意: 情報源コードの名前を解決できないため都道府県欄を空にします", file=sys.stderr)

    text = readme.read_text(encoding="utf-8")
    text = replace_block(text, "dataset", dataset_table(ds))
    text = replace_block(text, "lowjoin", low_join_table(ds, report, names))
    readme.write_text(text, encoding="utf-8")
    print(f"更新: {readme}（対象年月 {ds['対象年月_表示']}）")
