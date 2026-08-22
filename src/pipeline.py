#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""パイプラインの入口。

  python3 src/pipeline.py check
  python3 src/pipeline.py run
  python3 src/pipeline.py run --from join
  python3 src/pipeline.py fetch|cycle|html|position|join|tiles|docs

このファイルのあるディレクトリが sys.path に入るため、jartic_signal をそのまま import できる。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jartic_signal.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
