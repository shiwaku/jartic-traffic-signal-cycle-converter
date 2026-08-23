# -*- coding: utf-8 -*-
"""交差点位置情報のHTML解析と、ページ↔情報源コードの割当。

北海道は5方面に分かれていて、位置情報ページの並びと JARTIC の都市の並びが一致しない。
そのため交差点番号の一致数で対応を選び直している。ここが崩れると座標が別の県に付く。
"""
import unittest

import helper  # noqa: F401
from jartic_signal import fetch, position


class TestPageName(unittest.TestCase):
    def test_都道府県のみ(self):
        self.assertEqual(fetch.page_name("R02"), "index10_2.html")
        self.assertEqual(fetch.page_name("R13"), "index10_13.html")

    def test_北海道は方面番号が付く(self):
        self.assertEqual(fetch.page_name("R01_1"), "index10_1_1.html")
        self.assertEqual(fetch.page_name("R01_5"), "index10_1_5.html")

    def test_ゼロ埋めは落とす(self):
        self.assertEqual(fetch.page_name("R09"), "index10_9.html")

    def test_都道府県番号(self):
        self.assertEqual(position.pref_no("R01_3"), 1)
        self.assertEqual(position.pref_no("R47"), 47)


class TestParseOptions(unittest.TestCase):
    def test_交差点番号はvalueではなくタグのテキスト(self):
        # value は全国通しの連番。制御情報の交差点番号はテキスト側（函館は value=263 / 番号=1）
        html = '<select><option value="263" lon="140.7" lat="41.7">1</option></select>'
        self.assertEqual(position.parse_options(html), [("1", "140.7", "41.7")])

    def test_座標の無い選択肢は捨てる(self):
        html = '<option value="">－</option><option value="1" lon="139.7" lat="35.6">10</option>'
        self.assertEqual(position.parse_options(html), [("10", "139.7", "35.6")])

    def test_属性の順序や引用符が違っても読める(self):
        html = "<option lat='35.6' value=\"1\" lon='139.7'>10</option>"
        self.assertEqual(position.parse_options(html), [("10", "139.7", "35.6")])

    def test_該当が無ければ空(self):
        self.assertEqual(position.parse_options("<html><body>なし</body></html>"), [])


class TestAssignment(unittest.TestCase):
    """ページ側の交差点番号の集合と、制御情報側の集合が最もよく重なる対応を選ぶ。"""

    def setUp(self):
        # ページの並び（1〜5方面）と情報源コードの並びがずれている状況を作る
        self.pages = ["p1", "p2", "p3"]
        self.page_nums = {
            "p1": {"1", "2", "3"},
            "p2": {"10", "11", "12"},
            "p3": {"20", "21", "22"},
        }
        self.code_nums = {
            "A": {"10", "11", "12"},   # p2 に対応
            "B": {"20", "21", "22"},   # p3 に対応
            "C": {"1", "2", "3"},      # p1 に対応
        }

    def test_総当たりで正しい対応を選ぶ(self):
        order, score = position.best_assignment(self.pages, ["A", "B", "C"],
                                                self.page_nums, self.code_nums)
        self.assertEqual(order, ("C", "A", "B"))
        self.assertEqual(score, 9)

    def test_貪欲法でも同じ答えになる(self):
        order, score = position.greedy_assignment(self.pages, ["A", "B", "C"],
                                                  self.page_nums, self.code_nums)
        self.assertEqual(order, ("C", "A", "B"))
        self.assertEqual(score, 9)

    def test_コードが多いときは貪欲法に切り替わる(self):
        # 8件は 40320 通り。総当たりを避ける分岐に入ることを確かめる
        pages = [f"p{i}" for i in range(8)]
        codes = [f"c{i}" for i in range(8)]
        page_nums = {f"p{i}": {str(i)} for i in range(8)}
        code_nums = {f"c{i}": {str(i)} for i in range(8)}
        self.assertGreater(len(codes), position.MAX_PERMUTATION_CODES)
        order, score = position.best_assignment(pages, codes, page_nums, code_nums)
        self.assertEqual(order, tuple(codes))
        self.assertEqual(score, 8)

    def test_1ページ1コードなら素通り(self):
        order, score = position.best_assignment(["p1"], ["C"], self.page_nums, self.code_nums)
        self.assertEqual(order, ("C",))
        self.assertEqual(score, 3)

    def test_一致が無いときも対応は返す(self):
        # 呼び出し側が hit==0 を見て中断する。ここでは落ちないことだけを確かめる
        order, score = position.best_assignment(["p1"], ["Z"], self.page_nums, {"Z": set()})
        self.assertEqual(order, ("Z",))
        self.assertEqual(score, 0)


if __name__ == "__main__":
    unittest.main()
