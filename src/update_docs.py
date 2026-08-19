# -*- coding: utf-8 -*-
"""dataset.json / join_report.json から README の収録データ節を書き換える。

対象年月や交差点数を人が転記すると、データだけ更新して文言が古いまま残る。
README 側にマーカーを置き、その中身だけを生成する。

  <!-- dataset:begin --> … <!-- dataset:end -->   収録データの表
  <!-- lowjoin:begin --> … <!-- lowjoin:end -->   結合率が低い情報源コードの表

情報源コードと都道府県の対応は**カタログの並び順から推測してはいけない**（実測で 3010=埼玉 /
3011=千葉 であり、並び順どおりではない）。zip の中身から得た source_codes.json とカタログを
突き合わせて求め、結果を data/source_names.json に残して次回以降の表示に使う。

使い方:
  python3 src/update_docs.py --dataset data/dataset.json --report data/join_report.json \
      --codes work/source_codes.json --catalog work/zip/catalog.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

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


def build_code_names(catalog_path: Path, codes_path: Path) -> dict:
    """情報源コード → 表示名（例: 3001 → 北海道（札幌）、301C → 三重）。

    zip 名（typeC_{都市}_{年}_{月}.zip）とカタログの id を突き合わせて求める。zip の中に
    どのコードが入っていたかは source_codes.json が持っているので、推測は入らない。
    """
    if not (catalog_path and catalog_path.exists() and codes_path and codes_path.exists()):
        return {}
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    zip_codes = json.loads(codes_path.read_text(encoding="utf-8"))
    names = {}
    for target in catalog.get("targetList", []):
        filename = target["link"].split("/")[-1]
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="data/dataset.json")
    p.add_argument("--report", default="data/join_report.json")
    p.add_argument("--readme", default="README.md")
    p.add_argument("--codes", default="work/source_codes.json")
    p.add_argument("--catalog", default="work/zip/catalog.json")
    p.add_argument("--names", default="data/source_names.json",
                   help="情報源コード → 都道府県名。解決できたら更新し、できなければ読む")
    args = p.parse_args()

    ds = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))

    names_path = Path(args.names)
    names = build_code_names(Path(args.catalog), Path(args.codes))
    if names:
        names_path.parent.mkdir(parents=True, exist_ok=True)
        names_path.write_text(json.dumps(names, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    elif names_path.exists():
        names = json.loads(names_path.read_text(encoding="utf-8"))
        print(f"注意: zip が無いため {names_path} の対応表を使います", file=sys.stderr)
    else:
        print("注意: 情報源コードの名前を解決できないため都道府県欄を空にします", file=sys.stderr)

    readme = Path(args.readme)
    text = readme.read_text(encoding="utf-8")
    text = replace_block(text, "dataset", dataset_table(ds))
    text = replace_block(text, "lowjoin", low_join_table(ds, report, names))
    readme.write_text(text, encoding="utf-8")
    print(f"更新: {readme}（対象年月 {ds['対象年月_表示']}）")


if __name__ == "__main__":
    main()
