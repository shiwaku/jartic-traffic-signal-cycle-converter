# -*- coding: utf-8 -*-
"""交差点制御情報の月次更新を1コマンドで通し、品質ゲートを通ったものだけを成果物にする。

JARTIC は最新1か月分しか配布せず、過去月のURLは消える。したがって

  * 生データの取得は取り逃すと復旧できない（アーカイブは公開判断より先に済ませる）
  * 更新の有無はカタログJSONの対象年月を見て判断する（日付から推測しない）

の2点を前提にしている。

サブコマンド:
  check   カタログを見て、公開済みデータより新しい月が出ているかだけを判定する（数秒）
  run     全段階を通し、ゲートを通れば data/ を更新する
  fetch / cycle / html / position / join / tiles / docs   段階ごとの実行
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import catalog, cycle, fetch, gate, join, position, report, tiles
from .paths import DataPaths, WorkPaths

ROOT = Path(__file__).resolve().parent.parent.parent

# run が通す段階。--from はこの並びの途中から始める。
STAGES = ["fetch", "cycle", "html", "position", "join", "tiles"]


def emit_github_output(**kwargs) -> None:
    """GitHub Actions の step output に書き出す（ローカル実行時は何もしない）。"""
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for k, v in kwargs.items():
            f.write(f"{k}={v}\n")


def banner(step: str) -> None:
    print(f"\n=== {step} ===", flush=True)


def required_inputs(work: WorkPaths, stage: str) -> list:
    """その段階から始めるために、前段が残しておくべき成果物。

    20分走ってから「前段の出力が無い」と気づくのを避けるため、開始前に確かめる。
    """
    return {
        "fetch": [],
        "cycle": [work.catalog],
        "html": [work.catalog, work.average_csv],
        "position": [work.catalog, work.average_csv, work.source_codes, work.html_dir],
        "join": [work.average_csv, work.position_csv],
        "tiles": [work.geojsonl, work.join_summary, work.catalog],
    }[stage]


# ---- check ----

def cmd_check(args: argparse.Namespace) -> int:
    entry = catalog.fetch_entry()
    month = catalog.normalize_month(entry.get("targetMonth", ""))
    day = catalog.normalize_day(entry.get("releaseDay", ""))
    current = report.load_json(Path(args.dataset)).get("対象年月", "")

    updated = month > current
    print(f"カタログ: 対象年月={month} 公開日={day} ファイル数={len(entry.get('targetList', []))}")
    print(f"公開済み: 対象年月={current or '(なし)'}")
    print("→ 更新あり" if updated else "→ 更新なし")
    if current and month < current:
        print(f"警告: カタログの対象年月が公開済みより古い（{month} < {current}）", file=sys.stderr)

    emit_github_output(updated=str(updated).lower(), target_month=month, release_day=day,
                       current_month=current)
    return 0


# ---- 段階ごと ----

def cmd_fetch(args: argparse.Namespace) -> int:
    fetch.download_zips(WorkPaths(args.work), workers=args.workers)
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    cycle.run(WorkPaths(args.work))
    return 0


def cmd_html(args: argparse.Namespace) -> int:
    fetch.download_pages(WorkPaths(args.work), workers=args.workers)
    return 0


def cmd_position(args: argparse.Namespace) -> int:
    position.run(WorkPaths(args.work))
    return 0


def cmd_join(args: argparse.Namespace) -> int:
    join.run(WorkPaths(args.work))
    return 0


def cmd_tiles(args: argparse.Namespace) -> int:
    tiles.run(WorkPaths(args.work))
    return 0


def cmd_docs(args: argparse.Namespace) -> int:
    report.update_readme(Path(args.readme), DataPaths(args.data_dir), WorkPaths(args.work))
    return 0


# ---- run ----

def cmd_run(args: argparse.Namespace) -> int:
    work = WorkPaths(args.work)
    data = DataPaths(args.data_dir)
    work.mkdirs()
    data.mkdirs()

    start = STAGES.index(args.from_stage)
    tippecanoe = tiles.find_tippecanoe()  # 20分走ってから無いと気づくのを避ける
    todo = STAGES[start:]
    if start:
        missing = [str(p) for p in required_inputs(work, args.from_stage) if not p.exists()]
        if missing:
            raise SystemExit(f"{args.from_stage} から再開するには次が必要です: {', '.join(missing)}")
        print(f"{args.from_stage} から再開します（{', '.join(STAGES[:start])} は既存の "
              f"{work.root} を使う）")

    for i, stage in enumerate(todo, 1):
        banner(f"{i}/{len(todo)} {stage}")
        if stage == "fetch":
            fetch.download_zips(work, workers=args.workers)
        elif stage == "cycle":
            cycle.run(work)
        elif stage == "html":
            fetch.download_pages(work, workers=args.workers)
        elif stage == "position":
            position.run(work)
        elif stage == "join":
            join.run(work)
        elif stage == "tiles":
            tiles.run(work, tippecanoe)

    # 結合の要約はチェックポイントから読む。--from tiles でも結合をやり直さずに済む。
    join_out = report.load_json(work.join_summary)
    if not join_out:
        raise SystemExit(f"{work.join_summary} がありません（join から流し直してください）")

    entry = catalog.load_entry(work.catalog)
    year_month = catalog.normalize_month(entry["targetMonth"])
    print(f"\n対象年月: {year_month}（公開 {catalog.normalize_day(entry['releaseDay'])}）")

    dataset = report.build_dataset(
        year_month=year_month,
        release_day=catalog.normalize_day(entry["releaseDay"]),
        report=join_out["report"],
        quality=join_out["quality"],
        total_rows=report.count_rows(work.average_csv),
        joined_rows=report.count_rows(work.joined_csv),
        pmtiles=work.pmtiles,
    )

    old_dataset = report.load_json(data.dataset)
    old_report = report.load_json(data.join_report)

    banner("品質ゲート")
    th = gate.Thresholds(
        max_intersection_drop=args.max_intersection_drop,
        max_join_rate_drop=args.max_join_rate_drop,
        max_median_shift=args.max_median_shift,
        max_tile_size_shift=args.max_tile_size_shift,
    )
    violations = gate.check(dataset, old_dataset, join_out["report"], th)
    for v in violations:
        print(f"  NG: {v}", file=sys.stderr)
    if violations and not args.force:
        emit_github_output(gate="fail", target_month=year_month, violations="; ".join(violations))
        print("\nゲートに落ちたため data/ は更新しません（--force で無視できます）", file=sys.stderr)
        print(f"生成物は {work.root} に残しています", file=sys.stderr)
        return 2
    print("  OK: 公開してよい状態です" if not violations else "  警告: --force でゲートを無視しました")

    diff = gate.source_code_diff(join_out["report"], old_report)
    for code, before, after, delta in diff:
        print(f"  情報源コード {code}: {before}% → {after}%（{delta:+.1f}pt）")

    report.write_texts(work, dataset, diff)

    shutil.copy2(work.join_report, data.join_report)
    shutil.copy2(work.hourly_stats, data.hourly_stats)
    data.dataset.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    if args.pmtiles_out:
        shutil.copy2(work.pmtiles, args.pmtiles_out)

    banner("ドキュメントの更新")
    report.update_readme(Path(args.readme), data, work)

    print(f"\n完了: {dataset['対象年月_表示']} / 交差点 {dataset['交差点数']:,}箇所 / "
          f"{dataset['レコード数']:,}レコード / 結合率 {dataset['行の結合率']}%")
    emit_github_output(gate="pass", target_month=year_month, pmtiles=str(work.pmtiles),
                       summary=f"{dataset['対象年月_表示']} 交差点{dataset['交差点数']}箇所 "
                               f"結合率{dataset['行の結合率']}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipeline", description=(__doc__ or "").splitlines()[0])
    p.add_argument("--work", default="work", help="中間ファイルの置き場所")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="新しい月が公開されているかだけを見る")
    c.add_argument("--dataset", default="data/dataset.json")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("run", help="全段階を通してゲートを通れば data/ を更新する")
    r.add_argument("--data-dir", default="data")
    r.add_argument("--readme", default=str(ROOT / "README.md"))
    r.add_argument("--pmtiles-out", default="", help="PMTiles の複製先（既定は複製しない）")
    r.add_argument("--from", dest="from_stage", choices=STAGES, default="fetch",
                   help="この段階から再開する（前段の成果物は work/ の既存分を使う）")
    r.add_argument("--force", action="store_true", help="ゲート違反を無視して data/ を更新する")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--max-intersection-drop", type=float, default=5.0)
    r.add_argument("--max-join-rate-drop", type=float, default=2.0)
    r.add_argument("--max-median-shift", type=float, default=10.0)
    r.add_argument("--max-tile-size-shift", type=float, default=50.0)
    r.set_defaults(func=cmd_run)

    stages = [
        ("fetch", "交差点制御情報の zip を一括ダウンロード", cmd_fetch, True),
        ("cycle", "時間帯別の平均サイクル長を算出", cmd_cycle, False),
        ("html", "交差点位置情報の HTML を取得", cmd_html, True),
        ("position", "HTML から交差点番号と座標を抽出", cmd_position, False),
        ("join", "座標を付与して GeoJSON・レポート・時間帯別統計を出力", cmd_join, False),
        ("tiles", "PMTiles を生成", cmd_tiles, False),
    ]
    for name, help_text, func, needs_workers in stages:
        s = sub.add_parser(name, help=help_text)
        if needs_workers:
            s.add_argument("--workers", type=int, default=4)
        s.set_defaults(func=func)

    d = sub.add_parser("docs", help="dataset.json から README の収録データ節を生成")
    d.add_argument("--data-dir", default="data")
    d.add_argument("--readme", default=str(ROOT / "README.md"))
    d.set_defaults(func=cmd_docs)

    return p


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
