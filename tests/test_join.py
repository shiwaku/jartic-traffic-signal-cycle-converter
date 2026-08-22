# -*- coding: utf-8 -*-
"""座標の結合、wide 形式の書き出し、時間帯別統計、品質指標。"""
import json
import tempfile
import unittest
from pathlib import Path

import helper  # noqa: F401
from jartic_signal import join

AVERAGE_HEADER = "情報源コード,交差点番号,年月,時間帯,平均サイクル長\n"


def average_csv(path, rows):
    path.write_text(AVERAGE_HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")


def full_day(code, no, base):
    """24時間分の行。時刻ごとに base + 時 の値を入れる。"""
    return [f"{code},{no},202606,{h:02d}:00,{base + h}.00" for h in range(24)]


class TestJoin(unittest.TestCase):
    def run_join(self, rows, positions):
        d = Path(self.tmp.name)
        average_csv(d / "average.csv", rows)
        return join.join(d / "average.csv", positions, d / "joined.csv")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_24時間分が1交差点にまとまる(self):
        r = self.run_join(full_day("3010", "1", 100), {("3010", "1"): ("139.7", "35.6")})
        self.assertEqual(len(r.by_intersection), 1)
        self.assertEqual(len(r.by_intersection[("3010", "1")]), 24)
        self.assertEqual(r.matched, 24)
        self.assertEqual(r.total, 24)

    def test_小数は整数秒に丸める(self):
        # Python の round() は偶数丸め。253,031 件の中央値・四分位を取るので、
        # 上方に偏る五捨五超入より偏りの出ない偶数丸めのほうが都合がよい。
        r = self.run_join(["3010,1,202606,07:00,120.49", "3010,1,202606,08:00,120.50",
                           "3010,1,202606,09:00,121.50", "3010,1,202606,10:00,120.51"],
                          {("3010", "1"): ("139.7", "35.6")})
        hours = r.by_intersection[("3010", "1")]
        self.assertEqual(hours[7], 120)
        self.assertEqual(hours[8], 120)   # 120.50 → 偶数側の 120
        self.assertEqual(hours[9], 122)   # 121.50 → 偶数側の 122
        self.assertEqual(hours[10], 121)

    def test_座標が無い交差点は落とし記録する(self):
        r = self.run_join(["3010,1,202606,07:00,120.00", "3010,999,202606,07:00,130.00"],
                          {("3010", "1"): ("139.7", "35.6")})
        self.assertEqual(r.matched, 1)
        self.assertEqual(r.total, 2)
        self.assertEqual(r.missing_keys, {("3010", "999")})

    def test_情報源コードが違えば別の交差点(self):
        r = self.run_join(["3010,1,202606,07:00,120.00", "3011,1,202606,07:00,130.00"],
                          {("3010", "1"): ("139.7", "35.6"), ("3011", "1"): ("140.1", "35.6")})
        self.assertEqual(len(r.by_intersection), 2)


class TestWriteGeojsonl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def build(self, rows, positions):
        average_csv(self.d / "average.csv", rows)
        r = join.join(self.d / "average.csv", positions, self.d / "joined.csv")
        out = self.d / "out.geojsonl"
        join.write_geojsonl(out, r)
        return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    def test_1交差点1フィーチャで属性はASCII短縮(self):
        feats = self.build(full_day("3010", "123", 100), {("3010", "123"): ("139.7", "35.6")})
        self.assertEqual(len(feats), 1)
        p = feats[0]["properties"]
        self.assertEqual(p["src"], "3010")
        self.assertEqual(p["no"], "123")
        self.assertEqual(p["c0"], 100)
        self.assertEqual(p["c23"], 123)
        self.assertEqual(feats[0]["geometry"]["coordinates"], [139.7, 35.6])

    def test_年月はフィーチャに持たせない(self):
        # 全レコードで同一なので dataset.json 側に持つ
        feats = self.build(full_day("3010", "1", 100), {("3010", "1"): ("139.7", "35.6")})
        self.assertNotIn("年月", feats[0]["properties"])

    def test_欠測の時間帯はキーごと省く(self):
        rows = ["3010,1,202606,07:00,120.00", "3010,1,202606,09:00,130.00"]
        feats = self.build(rows, {("3010", "1"): ("139.7", "35.6")})
        p = feats[0]["properties"]
        self.assertIn("c7", p)
        self.assertIn("c9", p)
        self.assertNotIn("c8", p)

    def test_派生値はタイルに入れない(self):
        # 24個の値から JS 側で計算できる。入れるとタイルが 0.7MB 増える
        feats = self.build(full_day("3010", "1", 100), {("3010", "1"): ("139.7", "35.6")})
        for key in ("cmin", "cmax", "cavg", "cpeak"):
            self.assertNotIn(key, feats[0]["properties"])


class TestHourlyStats(unittest.TestCase):
    def make(self, by_intersection):
        r = join.JoinResult()
        r.by_intersection = by_intersection
        return r

    def test_時間帯ごとの四分位(self):
        # 7時に 100..199 の100件
        r = self.make({("3010", str(i)): {7: 100 + i} for i in range(100)})
        stats = join.hourly_stats(r)
        seven = stats[7]
        self.assertEqual(seven["件数"], 100)
        self.assertEqual(seven["p25"], 125)
        self.assertEqual(seven["中央値"], 150)
        self.assertEqual(seven["p75"], 175)

    def test_24時間分を必ず返す(self):
        r = self.make({("3010", "1"): {7: 120}})
        stats = join.hourly_stats(r)
        self.assertEqual(len(stats), 24)
        self.assertEqual(stats[0]["件数"], 0)
        self.assertNotIn("中央値", stats[0])
        self.assertEqual(stats[7]["中央値"], 120)


class TestQuality(unittest.TestCase):
    def make(self, by_intersection, coords=None):
        r = join.JoinResult()
        r.by_intersection = by_intersection
        r.coords = coords or {k: (139.7, 35.6) for k in by_intersection}
        return r

    def test_健全なデータ(self):
        by = {("3010", str(i)): {h: 120 for h in range(24)} for i in range(3)}
        q = join.quality(self.make(by))
        self.assertEqual(q["サイクル長中央値"], 120)
        self.assertEqual(q["値域外レコード数"], 0)
        self.assertEqual(q["時間帯が欠けている交差点数"], 0)
        self.assertEqual(q["範囲外の座標数"], 0)

    def test_値域外を数える(self):
        by = {("3010", "1"): {0: 10, 1: 120, 2: 500}}
        q = join.quality(self.make(by))
        self.assertEqual(q["値域外レコード数"], 2)   # 10 と 500

    def test_時間帯が欠けている交差点を数える(self):
        by = {
            ("3010", "1"): {h: 120 for h in range(24)},
            ("3010", "2"): {h: 120 for h in range(23)},
        }
        self.assertEqual(join.quality(self.make(by))["時間帯が欠けている交差点数"], 1)

    def test_日本の範囲外の座標を数える(self):
        by = {("3010", "1"): {0: 120}, ("3010", "2"): {0: 120}}
        coords = {("3010", "1"): (139.7, 35.6), ("3010", "2"): (0.0, 0.0)}
        self.assertEqual(join.quality(self.make(by, coords))["範囲外の座標数"], 1)

    def test_空でも落ちない(self):
        q = join.quality(self.make({}))
        self.assertEqual(q["サイクル長中央値"], 0)


class TestBuildReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def test_情報源コード別の結合率(self):
        rows = ["3010,1,202606,07:00,120.00", "3010,2,202606,07:00,120.00",
                "3011,1,202606,07:00,120.00"]
        average_csv(self.d / "average.csv", rows)
        positions = {("3010", "1"): ("139.7", "35.6"), ("3011", "1"): ("140.1", "35.6")}
        r = join.join(self.d / "average.csv", positions, self.d / "joined.csv")
        report = join.build_report(self.d / "average.csv", r)

        self.assertEqual(report["制御情報の交差点数"], 3)
        self.assertEqual(report["位置情報が付与された交差点数"], 2)
        self.assertEqual(report["対象年月"], ["202606"])
        by_code = {c["情報源コード"]: c for c in report["情報源コード別"]}
        self.assertEqual(by_code["3010"]["結合率"], 50.0)
        self.assertEqual(by_code["3011"]["結合率"], 100.0)


if __name__ == "__main__":
    unittest.main()
