# -*- coding: utf-8 -*-
"""交差点制御情報の月次更新を1コマンドで通し、品質ゲートを通ったものだけを成果物にする。

JARTIC は最新1か月分しか配布せず、過去月のURLは消える。したがって

  * 生データの取得は取り逃すと復旧できない（アーカイブは公開判断より先に済ませる）
  * 更新の有無はカタログJSONの対象年月を見て判断する（日付から推測しない）

の2点を前提にしている。

サブコマンド:
  check  カタログを見て、公開済みデータより新しい月が出ているかだけを判定する（数秒）
  run    ダウンロードから PMTiles 生成までを通し、ゲートを通れば data/ を更新する

使い方:
  python3 src/run_pipeline.py check
  python3 src/run_pipeline.py run --work work
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
CATALOG_URL = "https://www.jartic.or.jp/d/opendata/opendata.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; jartic-traffic-signal-cycle-converter)"}
JST = timezone(timedelta(hours=9))

# 品質ゲートの既定値。人のレビューを挟まずに公開するため、ここが唯一の防波堤になる。
MAX_INTERSECTION_DROP = 5.0   # 交差点数の前回比（%）
MAX_JOIN_RATE_DROP = 2.0      # 行の結合率の前回比（ポイント）


# ---- カタログ ----

def fetch_catalog_entry(url: str = CATALOG_URL) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        catalog = json.load(r)
    for entry in catalog:
        if entry.get("type") == "typeC":
            return entry
    raise SystemExit("カタログに typeC（交差点制御情報）が見つかりません")


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


def load_dataset(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def emit_github_output(**kwargs) -> None:
    """GitHub Actions の step output に書き出す（ローカル実行時は何もしない）。"""
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for k, v in kwargs.items():
            f.write(f"{k}={v}\n")


# ---- check ----

def cmd_check(args: argparse.Namespace) -> int:
    entry = fetch_catalog_entry()
    month = normalize_month(entry.get("targetMonth", ""))
    day = normalize_day(entry.get("releaseDay", ""))
    current = load_dataset(Path(args.dataset)).get("対象年月", "")

    updated = month > current
    print(f"カタログ: 対象年月={month} 公開日={day} ファイル数={len(entry.get('targetList', []))}")
    print(f"公開済み: 対象年月={current or '(なし)'}")
    print("→ 更新あり" if updated else "→ 更新なし")
    if current and month < current:
        print(f"警告: カタログの対象年月が公開済みより古い（{month} < {current}）", file=sys.stderr)

    emit_github_output(updated=str(updated).lower(), target_month=month, release_day=day,
                       current_month=current)
    return 0


# ---- run ----

def sh(cmd: list, step: str) -> None:
    print(f"\n=== {step} ===\n$ {' '.join(str(c) for c in cmd)}", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"{step} が失敗しました（exit {r.returncode}）")


def count_rows(path: Path) -> int:
    """ヘッダーを除いた行数。"""
    with path.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


def check_gates(new: dict, old: dict, new_report: dict, args: argparse.Namespace) -> list:
    """公開してよいかを判定し、違反の一覧を返す（空なら通過）。"""
    violations = []

    if old:
        if new["対象年月"] <= old.get("対象年月", ""):
            violations.append(
                f"対象年月が進んでいない（今回 {new['対象年月']} / 前回 {old.get('対象年月')}）")

        old_n = old.get("交差点数") or 0
        if old_n:
            drop = (old_n - new["交差点数"]) / old_n * 100
            if drop > args.max_intersection_drop:
                violations.append(
                    f"交差点数が前回比 -{drop:.1f}%（{old_n:,} → {new['交差点数']:,}、"
                    f"許容 -{args.max_intersection_drop}%）")

        old_rate = old.get("行の結合率")
        if old_rate is not None:
            drop = old_rate - new["行の結合率"]
            if drop > args.max_join_rate_drop:
                violations.append(
                    f"行の結合率が前回比 -{drop:.2f}pt（{old_rate}% → {new['行の結合率']}%、"
                    f"許容 -{args.max_join_rate_drop}pt）")

    zero = [c["情報源コード"] for c in new_report.get("情報源コード別", [])
            if c["制御情報の交差点数"] and c["位置情報あり"] == 0]
    if zero:
        violations.append(f"位置情報が1件も結合できない情報源コード: {', '.join(zero)}")

    return violations


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


def write_texts(work: Path, ds: dict, diff: list) -> None:
    """Release ノートとコミットメッセージを work/ に書き出す。"""
    lines = [
        f"対象年月 {ds['対象年月_表示']}（JARTIC公開 {ds['公開日']}）",
        f"交差点 {ds['交差点数']:,}箇所（うち座標付与 {ds['位置情報が付与された交差点数']:,}）",
        f"{ds['レコード数']:,}レコード / 行の結合率 {ds['行の結合率']}%",
    ]
    if diff:
        lines += ["", "情報源コード別の結合率の変化:"]
        lines += [f"- {code}: {before}% → {after}%（{delta:+.1f}pt）"
                  for code, before, after, delta in diff]
    (work / "release_notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    commit = [f"データを{ds['対象年月']}分に更新", "",
              f"交差点 {ds['交差点数']:,}箇所 / {ds['レコード数']:,}レコード / "
              f"結合率 {ds['行の結合率']}%",
              f"PMTiles は Release data-{ds['対象年月']} に添付。生zipは退避済み。"]
    (work / "commit_message.txt").write_text("\n".join(commit) + "\n", encoding="utf-8")


def cmd_run(args: argparse.Namespace) -> int:
    work = Path(args.work)
    data_dir = Path(args.data_dir)
    work.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    tippecanoe = shutil.which("tippecanoe")
    if not tippecanoe:
        raise SystemExit("tippecanoe が見つかりません（https://github.com/felt/tippecanoe）")

    py = sys.executable
    zip_dir = work / "zip"

    if args.skip_download:
        print("ダウンロードをスキップします（--skip-download）")
    else:
        sh([py, str(SRC / "jartic_opendata_kousaten_dl.py"), "--out", str(zip_dir)],
           "1/6 交差点制御情報のダウンロード")

    catalog = json.loads((zip_dir / "catalog.json").read_text(encoding="utf-8"))
    year_month = normalize_month(catalog["targetMonth"])
    print(f"対象年月: {year_month}（公開 {normalize_day(catalog['releaseDay'])}）")

    sh([py, str(SRC / "calc_average_cycle.py"), "--zip-dir", str(zip_dir), "--out", str(work)],
       "2/6 平均サイクル長の算出")
    sh([py, str(SRC / "intersection_position_getHTML.py"),
        "--catalog", str(zip_dir / "catalog.json"), "--out", str(work / "html")],
       "3/6 交差点位置情報のHTML取得")
    sh([py, str(SRC / "HTMLtoCSV.py"), "--catalog", str(zip_dir / "catalog.json"),
        "--source-codes", str(work / "source_codes.json"),
        "--average", str(work / "national_average_cycle.csv"),
        "--html", str(work / "html"), "--out", str(work)],
       "4/6 交差点番号と座標の抽出")

    # レポートは work に出し、ゲートを通ってから data/ に反映する。
    new_report_path = work / "join_report.json"
    sh([py, str(SRC / "csvfile-add-latlon.py"),
        "--average", str(work / "national_average_cycle.csv"),
        "--position", str(work / "intersection_position.csv"),
        "--out", str(work), "--report", str(new_report_path)],
       "5/6 座標の付与とレポート出力")

    # z13 の座標精度は約1.2mで交差点の位置には十分。z14 にすると 5.7MB → 7.0MB になるが
    # 見え方は変わらない。--drop-densest-as-needed は 1交差点1フィーチャなら実質発動
    # しないが、将来交差点が増えたときの保険として残す。
    new_pmtiles = work / "signal_cycle.pmtiles"
    sh([tippecanoe, "-o", str(new_pmtiles), "-l", "signal_cycle", "-Z0", "-z13", "-r1",
        "--drop-densest-as-needed", "--force", "-P", str(work / "signal_cycle.geojsonl")],
       "6/6 PMTiles の生成")

    report = json.loads(new_report_path.read_text(encoding="utf-8"))
    total_rows = count_rows(work / "national_average_cycle.csv")
    joined_rows = count_rows(work / "signal_cycle.csv")

    dataset = {
        "対象年月": year_month,
        "対象年月_表示": display_month(year_month),
        "公開日": normalize_day(catalog["releaseDay"]),
        "交差点数": report["制御情報の交差点数"],
        "位置情報が付与された交差点数": report["位置情報が付与された交差点数"],
        "レコード数": total_rows,
        "結合レコード数": joined_rows,
        "行の結合率": report["行の結合率"],
        "生成日時": datetime.now(JST).isoformat(timespec="seconds"),
        "出典": {
            "交差点制御情報": CATALOG_URL,
            "交差点位置情報": "https://www.tmt.or.jp/research/index10.html",
        },
    }

    dataset_path = data_dir / "dataset.json"
    old_dataset = load_dataset(dataset_path)
    old_report = json.loads((data_dir / "join_report.json").read_text(encoding="utf-8")) \
        if (data_dir / "join_report.json").exists() else {}

    print("\n=== 品質ゲート ===")
    violations = check_gates(dataset, old_dataset, report, args)
    for v in violations:
        print(f"  NG: {v}", file=sys.stderr)
    if violations and not args.force:
        emit_github_output(gate="fail", target_month=year_month,
                           violations="; ".join(violations))
        print("\nゲートに落ちたため data/ は更新しません（--force で無視できます）", file=sys.stderr)
        print(f"生成物は {work} に残しています", file=sys.stderr)
        return 2
    print("  OK: 公開してよい状態です" if not violations else "  警告: --force でゲートを無視しました")

    for code, before, after, delta in source_code_diff(report, old_report):
        print(f"  情報源コード {code}: {before}% → {after}%（{delta:+.1f}pt）")

    # Release ノートとコミットメッセージも成果物として書く。YAML の中に整形処理を
    # 持ち込まずに済み、ローカル実行でも同じ文面を確認できる。
    write_texts(work, dataset, source_code_diff(report, old_report))

    shutil.copy2(new_report_path, data_dir / "join_report.json")
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    if args.pmtiles_out:
        shutil.copy2(new_pmtiles, args.pmtiles_out)

    sh([py, str(SRC / "update_docs.py"), "--dataset", str(dataset_path),
        "--report", str(data_dir / "join_report.json"), "--readme", str(ROOT / "README.md"),
        "--codes", str(work / "source_codes.json"), "--catalog", str(zip_dir / "catalog.json"),
        "--names", str(data_dir / "source_names.json")],
       "ドキュメントの更新")

    print(f"\n完了: {dataset['対象年月_表示']} / 交差点 {dataset['交差点数']:,}箇所 / "
          f"{dataset['レコード数']:,}レコード / 結合率 {dataset['行の結合率']}%")
    emit_github_output(gate="pass", target_month=year_month,
                       pmtiles=str(new_pmtiles),
                       summary=f"{dataset['対象年月_表示']} 交差点{dataset['交差点数']}箇所 "
                               f"結合率{dataset['行の結合率']}%")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="新しい月が公開されているかだけを見る")
    c.add_argument("--dataset", default="data/dataset.json")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("run", help="パイプラインを通してゲートを通れば data/ を更新する")
    r.add_argument("--work", default="work")
    r.add_argument("--data-dir", default="data")
    r.add_argument("--pmtiles-out", default="", help="PMTiles の複製先（既定は複製しない）")
    r.add_argument("--skip-download", action="store_true", help="取得済みの work/zip を使う")
    r.add_argument("--force", action="store_true", help="ゲート違反を無視して data/ を更新する")
    r.add_argument("--max-intersection-drop", type=float, default=MAX_INTERSECTION_DROP)
    r.add_argument("--max-join-rate-drop", type=float, default=MAX_JOIN_RATE_DROP)
    r.set_defaults(func=cmd_run)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
