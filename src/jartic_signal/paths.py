# -*- coding: utf-8 -*-
"""段階間で受け渡すファイル名の契約。

以前は「work/ 配下のこの名前」という暗黙の取り決めが呼び出し側に散らばっていて、
名前を変えると追いきれなかった。ここだけを見れば全部の中間ファイルが分かる。
"""
from __future__ import annotations

from pathlib import Path


class WorkPaths:
    """中間ファイルの置き場所。リポジトリには含めない。"""

    def __init__(self, root: str | Path = "work") -> None:
        self.root = Path(root)

    def mkdirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.zip_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    # 取得
    @property
    def zip_dir(self) -> Path:
        return self.root / "zip"

    @property
    def catalog(self) -> Path:
        return self.zip_dir / "catalog.json"

    @property
    def html_dir(self) -> Path:
        return self.root / "html"

    # 集計
    @property
    def average_csv(self) -> Path:
        return self.root / "national_average_cycle.csv"

    @property
    def source_codes(self) -> Path:
        return self.root / "source_codes.json"

    @property
    def position_csv(self) -> Path:
        return self.root / "intersection_position.csv"

    # 結合と成果物
    @property
    def joined_csv(self) -> Path:
        return self.root / "signal_cycle.csv"

    @property
    def geojsonl(self) -> Path:
        return self.root / "signal_cycle.geojsonl"

    @property
    def pmtiles(self) -> Path:
        return self.root / "signal_cycle.pmtiles"

    @property
    def join_report(self) -> Path:
        return self.root / "join_report.json"

    @property
    def hourly_stats(self) -> Path:
        return self.root / "hourly_stats.json"

    @property
    def join_summary(self) -> Path:
        """結合段階のチェックポイント。--from tiles のように後段だけ流し直すとき、
        結合をやり直さずに要約を読み戻せるようにしている。"""
        return self.root / "join_summary.json"

    # 公開用の文面
    @property
    def release_notes(self) -> Path:
        return self.root / "release_notes.md"

    @property
    def commit_message(self) -> Path:
        return self.root / "commit_message.txt"


class DataPaths:
    """公開する成果物。品質ゲートを通ったときだけ書き換える。"""

    def __init__(self, root: str | Path = "data") -> None:
        self.root = Path(root)

    def mkdirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def dataset(self) -> Path:
        return self.root / "dataset.json"

    @property
    def join_report(self) -> Path:
        return self.root / "join_report.json"

    @property
    def hourly_stats(self) -> Path:
        return self.root / "hourly_stats.json"

    @property
    def source_names(self) -> Path:
        return self.root / "source_names.json"
