# -*- coding: utf-8 -*-
"""行区切りGeoJSON から PMTiles を生成する。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .paths import WorkPaths

# z13 の座標精度は約1.2mで交差点の位置には十分。z14 にすると 5.7MB → 7.0MB になるが
# 見え方は変わらない。--drop-densest-as-needed は 1交差点1フィーチャなら実質発動
# しないが、将来交差点が増えたときの保険として残す。
MIN_ZOOM = 0
MAX_ZOOM = 13
LAYER_NAME = "signal_cycle"


def find_tippecanoe() -> str:
    path = shutil.which("tippecanoe")
    if not path:
        raise SystemExit("tippecanoe が見つかりません（https://github.com/felt/tippecanoe）")
    return path


def build(geojsonl: Path, out: Path, tippecanoe: str | None = None) -> Path:
    cmd = [tippecanoe or find_tippecanoe(), "-o", str(out), "-l", LAYER_NAME,
           f"-Z{MIN_ZOOM}", f"-z{MAX_ZOOM}", "-r1",
           "--drop-densest-as-needed", "--force", "-P", str(geojsonl)]
    print("$ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"tippecanoe が失敗しました（exit {r.returncode}）")
    return out


def run(work: WorkPaths, tippecanoe: str | None = None) -> Path:
    return build(work.geojsonl, work.pmtiles, tippecanoe)
