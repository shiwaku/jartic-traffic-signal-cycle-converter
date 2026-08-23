# -*- coding: utf-8 -*-
"""制御CSVの集計。"""
import csv
import tempfile
import unittest
import zipfile
from collections import defaultdict
from pathlib import Path

import helper  # noqa: F401
from jartic_signal import cycle

# 実データの列: 時刻, 情報源コード, 交差点番号, サイクル長, スプリット＃1〜6, リンクバージョン
HEADER = "時刻,情報源コード,交差点番号,サイクル長,スプリット＃1,リンクバージョン"
ROWS = [
    "2026/06/01 07:15,3010,123,120,25,1",
    "2026/06/01 07:45,3010,123,140,25,1",
    "2026/06/01 08:15,3010,123,150,25,1",
    "2026/06/02 07:15,3010,456,100,25,1",
]


def totals_dict():
    return defaultdict(lambda: [0, 0])


class TestAccumulate(unittest.TestCase):
    def rows(self, lines):
        return [line.split(",") for line in lines]

    def test_同じ時間帯の値を平均するために合計と件数を持つ(self):
        totals, codes = totals_dict(), set()
        used = cycle.accumulate(self.rows(ROWS), totals, codes)
        self.assertEqual(used, 4)
        self.assertEqual(codes, {"3010"})
        # 7時台は 120 と 140 の2件
        self.assertEqual(totals[("3010", "123", "202606", "07")], [260, 2])
        self.assertEqual(totals[("3010", "123", "202606", "08")], [150, 1])
        self.assertEqual(totals[("3010", "456", "202606", "07")], [100, 1])

    def test_日をまたいでも同じ時間帯にまとまる(self):
        totals, codes = totals_dict(), set()
        cycle.accumulate(self.rows([
            "2026/06/01 07:15,3010,1,100,25,1",
            "2026/06/20 07:45,3010,1,200,25,1",
        ]), totals, codes)
        self.assertEqual(totals[("3010", "1", "202606", "07")], [300, 2])

    def test_サイクル長が空の行は捨てる(self):
        totals, codes = totals_dict(), set()
        used = cycle.accumulate(self.rows(["2026/06/01 07:15,3010,1,,25,1"]), totals, codes)
        self.assertEqual(used, 0)
        self.assertEqual(len(totals), 0)

    def test_サイクル長が数値でない行は捨てる(self):
        totals, codes = totals_dict(), set()
        used = cycle.accumulate(self.rows(["2026/06/01 07:15,3010,1,---,25,1"]), totals, codes)
        self.assertEqual(used, 0)

    def test_列が足りない行は捨てる(self):
        totals, codes = totals_dict(), set()
        used = cycle.accumulate([["2026/06/01 07:15", "3010", "1"]], totals, codes)
        self.assertEqual(used, 0)

    def test_情報源コードが違えば別の交差点として扱う(self):
        # 交差点番号は情報源コードごとの連番なので、単独では一意にならない
        totals, codes = totals_dict(), set()
        cycle.accumulate(self.rows([
            "2026/06/01 07:15,3010,1,100,25,1",
            "2026/06/01 07:15,3011,1,200,25,1",
        ]), totals, codes)
        self.assertEqual(len(totals), 2)
        self.assertEqual(codes, {"3010", "3011"})


class TestReadZip(unittest.TestCase):
    def make_zip(self, path, members):
        with zipfile.ZipFile(path, "w") as z:
            for name, body in members.items():
                z.writestr(name, body.encode("cp932"))

    def test_制御CSVだけを読みヘッダーを飛ばす(self):
        with tempfile.TemporaryDirectory() as d:
            zip_path = Path(d) / "typeC_test_2026_06.zip"
            self.make_zip(zip_path, {
                "20260601_制御_test.csv": HEADER + "\n" + "\n".join(ROWS) + "\n",
                # 同じ zip に「定義」CSV も入っている。列数も内容も違うので混ぜてはいけない。
                "20260601_定義_test.csv": "交差点番号,その他\n123,x\n",
            })
            rows = list(cycle.read_control_rows(zip_path))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0][1], "3010")


class TestZipMemberName(unittest.TestCase):
    """zip 内のファイル名は cp932 のバイト列で格納されていることがある。

    zipfile の書き出し側は非ASCII名に必ず UTF-8 フラグを立てるため、書いて読み直す形では
    再現できない。ZipInfo を直接組んで復元処理だけを確かめる。
    """

    def info(self, filename, utf8):
        i = zipfile.ZipInfo(filename)
        i.flag_bits = 0x800 if utf8 else 0
        return i

    def test_UTF8フラグがあればそのまま使う(self):
        name = "20260601_制御_test.csv"
        self.assertEqual(cycle.zip_member_name(self.info(name, utf8=True)), name)

    def test_フラグが無ければcp932として復元する(self):
        name = "20260601_制御_test.csv"
        stored = name.encode("cp932").decode("cp437")
        self.assertNotEqual(stored, name)
        self.assertEqual(cycle.zip_member_name(self.info(stored, utf8=False)), name)

    def test_復元できないときは元の名前を返す(self):
        # cp437 に無い文字が混ざっていると encode に失敗する。落とさず素通しさせる。
        self.assertEqual(cycle.zip_member_name(self.info("制御.csv", utf8=False)), "制御.csv")


class TestWriteAverageCsv(unittest.TestCase):
    def test_平均を小数2桁で書く(self):
        totals = {("3010", "123", "202606", "07"): [260, 2]}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "average.csv"
            cycle.write_average_csv(out, totals)
            with out.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["時間帯"], "07:00")
        self.assertEqual(rows[0]["平均サイクル長"], "130.00")


if __name__ == "__main__":
    unittest.main()
