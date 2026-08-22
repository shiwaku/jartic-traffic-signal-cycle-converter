# -*- coding: utf-8 -*-
"""HTTP 取得。UA とリトライを1か所に集める。

以前は同じリトライ処理が jartic_opendata_kousaten_dl.py と
intersection_position_getHTML.py に別々に書かれ、カタログの取得だけ
run_pipeline.py にもう1つあった。
"""
from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (compatible; jartic-traffic-signal-cycle-converter)"}
ATTEMPTS = 4


def get(url: str, timeout: int = 60, attempts: int = ATTEMPTS, label: str = "") -> bytes:
    """指数バックオフで再試行しながら取得する。応答が返らないまま接続が生き続けることが
    あるので、必ずタイムアウトを付けて打ち切る。"""
    name = label or url.rsplit("/", 1)[-1]
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # タイムアウト・切断・一時的なエラー
            if attempt == attempts:
                raise SystemExit(f"{name}: {attempts}回試みて取得できませんでした（{e}）")
            wait = 2 ** attempt
            print(f"  {name}: 取得失敗（{type(e).__name__}）。{wait}秒後に再試行 "
                  f"[{attempt}/{attempts - 1}]", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise SystemExit(f"{name}: 取得できませんでした")  # pragma: no cover


def download(url: str, dest: Path, timeout: int = 180, attempts: int = ATTEMPTS) -> int:
    """1ファイルを取得する。既に同サイズで存在すればスキップし、0 を返す。

    途中で切れた応答をそのまま書くと、次回「取得済み」と誤判定して壊れたzipが残るため、
    Content-Length と実際の長さが合わないときは失敗として扱う。
    """
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                size = int(r.headers.get("Content-Length", 0))
                if dest.exists() and dest.stat().st_size == size and size > 0:
                    return 0
                data = r.read()
            if size and len(data) != size:
                raise OSError(f"サイズ不一致 {len(data)} != {size}")
            dest.write_bytes(data)
            return dest.stat().st_size
        except Exception as e:
            if attempt == attempts:
                raise SystemExit(f"{dest.name}: {attempts}回試みて取得できませんでした（{e}）")
            wait = 2 ** attempt
            print(f"  {dest.name}: 取得失敗（{type(e).__name__}）。{wait}秒後に再試行 "
                  f"[{attempt}/{attempts - 1}]", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise SystemExit(f"{dest.name}: 取得できませんでした")  # pragma: no cover
