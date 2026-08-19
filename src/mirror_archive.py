# -*- coding: utf-8 -*-
"""Release に退避してある月次データを、ローカルのアーカイブへミラーする。

JARTIC は最新1か月分しか配布しないため、生zipは取得した月のうちに private リポジトリの
Release へ退避している（update-data ワークフロー）。このスクリプトはそこから未取得の月を
落としてきて、月ごとのディレクトリに並べる。Release 側は消えないので、実行が遅れても
取りこぼさない。

  {dest}/{年月}/zip/typeC_*.zip     生データ（JARTICの配布zipそのまま）
  {dest}/{年月}/catalog.json        取得時のカタログ
  {dest}/{年月}/signal_cycle.pmtiles, dataset.json, join_report.json   成果物
  {dest}/{年月}/sha256.txt          取り込み時に計算したハッシュ

gh コマンドの認証が必要（gh auth login 済みであること）。

使い方:
  python3 src/mirror_archive.py --raw-repo shiwaku/jartic-raw-archive
  python3 src/mirror_archive.py --raw-repo … --month 202606 --recheck
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = os.environ.get("JARTIC_ARCHIVE_DIR") or str(ROOT.parent / "jartic-archive")


def gh(args: list, capture: bool = True) -> str:
    r = subprocess.run(["gh", *args], capture_output=capture, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} が失敗しました: {(r.stderr or '').strip()}")
    return (r.stdout or "").strip()


def release_months(repo: str, prefix: str) -> list:
    """{prefix}YYYYMM のタグから年月を新しい順に返す。"""
    out = gh(["release", "list", "--repo", repo, "--limit", "200", "--json", "tagName"])
    tags = [r["tagName"] for r in json.loads(out or "[]")]
    return sorted({t[len(prefix):] for t in tags if t.startswith(prefix)}, reverse=True)


def sha256_dir(base: Path) -> str:
    lines = []
    for path in sorted(p for p in base.rglob("*") if p.is_file() and p.name != "sha256.txt"):
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {path.relative_to(base).as_posix()}")
    return "\n".join(lines) + "\n"


def mirror_month(month: str, dest: Path, raw_repo: str, data_repo: str, recheck: bool) -> bool:
    month_dir = dest / month
    manifest = month_dir / "sha256.txt"
    if manifest.exists() and not recheck:
        print(f"{month}: 取得済み（--recheck で再検証）")
        return False

    zip_dir = month_dir / "zip"
    zip_dir.mkdir(parents=True, exist_ok=True)
    print(f"{month}: 生データを取得中…", flush=True)
    gh(["release", "download", f"raw-{month}", "--repo", raw_repo,
        "--dir", str(zip_dir), "--clobber"], capture=False)

    catalog = zip_dir / "catalog.json"
    if catalog.exists():
        catalog.replace(month_dir / "catalog.json")

    if data_repo:
        print(f"{month}: 成果物を取得中…", flush=True)
        try:
            gh(["release", "download", f"data-{month}", "--repo", data_repo,
                "--dir", str(month_dir), "--clobber"], capture=False)
        except SystemExit as e:
            print(f"  成果物の Release が無いため省略します（{e}）", file=sys.stderr)

    manifest.write_text(sha256_dir(month_dir), encoding="utf-8")
    size = sum(p.stat().st_size for p in month_dir.rglob("*") if p.is_file())
    print(f"{month}: 完了  {len(list(zip_dir.glob('*.zip')))}ファイル  {size/1e6:.0f} MB")
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-repo", required=True, help="生zipを退避してある private リポジトリ")
    p.add_argument("--data-repo", default="shiwaku/jartic-traffic-signal-cycle-converter",
                   help="成果物の Release があるリポジトリ（空文字で省略）")
    p.add_argument("--dest", default=DEFAULT_DEST, help=f"保存先（既定 {DEFAULT_DEST}）")
    p.add_argument("--month", default="", help="特定の年月だけ（既定は未取得のすべて）")
    p.add_argument("--recheck", action="store_true", help="取得済みの月も落とし直して検証する")
    args = p.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    months = [args.month] if args.month else release_months(args.raw_repo, "raw-")
    if not months:
        raise SystemExit(f"{args.raw_repo} に raw-YYYYMM の Release がありません")

    fetched = 0
    for month in months:
        fetched += mirror_month(month, dest, args.raw_repo, args.data_repo, args.recheck)
    print(f"\n保存先: {dest}  新規取得 {fetched}か月 / 収録 {len(months)}か月", file=sys.stderr)


if __name__ == "__main__":
    main()
