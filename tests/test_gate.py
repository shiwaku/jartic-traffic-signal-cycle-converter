# -*- coding: utf-8 -*-
"""品質ゲートの判定。

人のレビューを挟まずに公開するため、ここが唯一の防波堤になる。しきい値の境目を
固定入力で確かめる。
"""
import unittest

import helper  # noqa: F401
from jartic_signal import gate

# 2026年6月の実データに合わせた「健全な」1件。各テストはここから必要な値だけ変える。
GOOD = {
    "対象年月": "202607",
    "交差点数": 10831,
    "位置情報が付与された交差点数": 10543,
    "レコード数": 259938,
    "結合レコード数": 253031,
    "行の結合率": 97.34,
    "サイクル長中央値": 120,
    "値域外レコード数": 0,
    "時間帯が欠けている交差点数": 1,
    "範囲外の座標数": 0,
    "PMTilesバイト数": 4949759,
}
PREV = dict(GOOD, 対象年月="202606")
REPORT = {"情報源コード別": [
    {"情報源コード": "3001", "制御情報の交差点数": 231, "位置情報あり": 231, "結合率": 100.0},
    {"情報源コード": "3010", "制御情報の交差点数": 1185, "位置情報あり": 1109, "結合率": 93.6},
]}


def check(new_patch=None, old_patch=None, report=None, th=None):
    new = dict(GOOD, **(new_patch or {}))
    old = None if old_patch == "none" else dict(PREV, **(old_patch or {}))
    return gate.check(new, old or {}, report if report is not None else REPORT, th)


class TestHealthy(unittest.TestCase):
    def test_健全なデータは通る(self):
        self.assertEqual(check(), [])

    def test_前回データが無くても絶対値の判定は効く(self):
        self.assertEqual(check(old_patch="none"), [])
        v = check({"範囲外の座標数": 3}, old_patch="none")
        self.assertEqual(len(v), 1)


class TestAgainstPrevious(unittest.TestCase):
    def test_対象年月が進んでいない(self):
        v = check({"対象年月": "202606"})
        self.assertTrue(any("対象年月が進んでいない" in x for x in v))

    def test_対象年月が戻っている(self):
        v = check({"対象年月": "202605"})
        self.assertTrue(any("対象年月が進んでいない" in x for x in v))

    def test_交差点数の減少はしきい値で切り替わる(self):
        # 既定 5%。10831 → 10300 は -4.90% で通り、10289 は -5.00% 超で落ちる
        self.assertEqual(check({"交差点数": 10300}), [])
        v = check({"交差点数": 10200})
        self.assertTrue(any("交差点数が前回比" in x for x in v))

    def test_交差点数が増えるのは通る(self):
        self.assertEqual(check({"交差点数": 12000}), [])

    def test_結合率の低下(self):
        self.assertEqual(check({"行の結合率": 95.5}), [])   # -1.84pt
        v = check({"行の結合率": 95.0})                      # -2.34pt
        self.assertTrue(any("行の結合率が前回比" in x for x in v))

    def test_中央値は増減どちらもみる(self):
        self.assertEqual(check({"サイクル長中央値": 129}), [])
        self.assertTrue(any("中央値" in x for x in check({"サイクル長中央値": 131})))
        self.assertTrue(any("中央値" in x for x in check({"サイクル長中央値": 109})))

    def test_タイルサイズの急変(self):
        self.assertEqual(check({"PMTilesバイト数": 7000000}), [])          # +41%
        v = check({"PMTilesバイト数": 1000000})                             # -80%
        self.assertTrue(any("PMTiles のサイズ" in x for x in v))

    def test_前回にタイルサイズが無ければ見ない(self):
        old = dict(PREV)
        del old["PMTilesバイト数"]
        self.assertEqual(gate.check(GOOD, old, REPORT), [])


class TestAbsolute(unittest.TestCase):
    def test_値域外レコードの割合(self):
        # 既定 0.1%。253031 件に対して 253 件（0.0999%）は通り、300 件で落ちる
        self.assertEqual(check({"値域外レコード数": 253}), [])
        v = check({"値域外レコード数": 300})
        self.assertTrue(any("妥当な範囲を外れる" in x for x in v))

    def test_時間帯が揃わない交差点の割合(self):
        # 既定 1%。10543 箇所に対して 105 件は通り、110 件で落ちる
        self.assertEqual(check({"時間帯が欠けている交差点数": 105}), [])
        v = check({"時間帯が欠けている交差点数": 110})
        self.assertTrue(any("24時間帯が揃わない" in x for x in v))

    def test_範囲外の座標は1件でも落とす(self):
        v = check({"範囲外の座標数": 1})
        self.assertTrue(any("日本の範囲外" in x for x in v))

    def test_位置情報が1件も結合できないコード(self):
        report = {"情報源コード別": [
            {"情報源コード": "301C", "制御情報の交差点数": 328, "位置情報あり": 0, "結合率": 0.0},
        ]}
        v = check(report=report)
        self.assertTrue(any("301C" in x for x in v))

    def test_制御情報が0件のコードは対象外(self):
        # 交差点が1つも無いコードは「結合できなかった」わけではない
        report = {"情報源コード別": [
            {"情報源コード": "9999", "制御情報の交差点数": 0, "位置情報あり": 0, "結合率": 0.0},
        ]}
        self.assertEqual(check(report=report), [])


class TestThresholds(unittest.TestCase):
    def test_しきい値を緩めれば通る(self):
        strict = check({"交差点数": 10200})
        self.assertTrue(strict)
        loose = check({"交差点数": 10200}, th=gate.Thresholds(max_intersection_drop=20.0))
        self.assertEqual(loose, [])

    def test_違反は積み上がる(self):
        v = check({"対象年月": "202606", "範囲外の座標数": 2, "サイクル長中央値": 200})
        self.assertEqual(len(v), 3)


class TestSourceCodeDiff(unittest.TestCase):
    def test_変化の大きい順に返す(self):
        old = {"情報源コード別": [
            {"情報源コード": "A", "結合率": 100.0},
            {"情報源コード": "B", "結合率": 90.0},
            {"情報源コード": "C", "結合率": 50.0},
        ]}
        new = {"情報源コード別": [
            {"情報源コード": "A", "結合率": 99.0},    # -1.0
            {"情報源コード": "B", "結合率": 95.0},    # +5.0
            {"情報源コード": "C", "結合率": 50.0},    # 変化なし
            {"情報源コード": "D", "結合率": 80.0},    # 前回に無い
        ]}
        rows = gate.source_code_diff(new, old)
        self.assertEqual([r[0] for r in rows], ["B", "A"])
        self.assertAlmostEqual(rows[0][3], 5.0)

    def test_上位N件に絞る(self):
        old = {"情報源コード別": [{"情報源コード": str(i), "結合率": 100.0} for i in range(10)]}
        new = {"情報源コード別": [{"情報源コード": str(i), "結合率": 100.0 - i} for i in range(10)]}
        self.assertEqual(len(gate.source_code_diff(new, old, top=3)), 3)


if __name__ == "__main__":
    unittest.main()
