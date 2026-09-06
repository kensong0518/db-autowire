# -*- coding: utf-8 -*-
"""意圖評分與 PTT 解析的單元測試：python3 -m unittest discover tests"""
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rr", os.path.join(BASE, "repair_radar.py"))
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

KW = rr.DEFAULT_KEYWORDS


def old(text, title="", author="tester", minutes_ago=600):
    """建立一則指定屋齡的貼文，避開「60 分鐘內 +10」干擾。"""
    return {
        "title": title,
        "body": text,
        "author": author,
        "posted_at": (datetime.now(rr.TPE) - timedelta(minutes=minutes_ago)).isoformat(),
    }


class TestScorer(unittest.TestCase):

    def test_典型求助文應達到推播門檻(self):
        p = old(
            "昨天不小心從腳踏車上摔下來，右上角整個裂開一條線，觸控目前還正常。"
            "想問一下台北或新北有沒有推薦的維修店，換總成大概要多少錢？",
            title="iPhone 14 螢幕摔破，台北有推薦的維修店嗎")
        score, hits = rr.score_post(p, KW)
        labels = [h[0] for h in hits]
        self.assertGreaterEqual(score, 70, "命中：%s" % labels)
        for expect in ("求助意圖", "故障描述", "裝置型號", "維修字眼", "雙北地區"):
            self.assertIn(expect, labels)

    def test_新文加分(self):
        """挑一則加總不會撞到 100 上限的貼文，才驗得出 +10。"""
        text = "螢幕邊邊有點翹起來，看起來是電池膨脹，不知道這樣還能不能繼續用。" * 2
        fresh = rr.score_post(old(text, "iPad 電池問題", minutes_ago=5), KW)[0]
        stale = rr.score_post(old(text, "iPad 電池問題", minutes_ago=600), KW)[0]
        self.assertLess(fresh, 100, "測試前提：這則不能撞到分數上限")
        self.assertEqual(fresh - stale, 10)

    def test_分數上限會夾住(self):
        text = ("洗澡放旁邊結果被水潑到，今天就開不了機了。請問這種進水的狀況送修還有機會救回來嗎？"
                "裡面照片沒備份比較急，中和附近可以的話最好。")
        self.assertEqual(rr.score_post(old(text, "Pixel 7 泡水求助", minutes_ago=5), KW)[0], 100)

    def test_已修好的回報文要被扣到門檻以下(self):
        p = old("上禮拜問的螢幕破裂問題，已經找到店家處理完了，換完跟新的一樣，價格也在預算內。感謝大家的建議。",
                title="感謝板友推薦，iPhone 螢幕已修好了")
        score, hits = rr.score_post(p, KW)
        self.assertIn("已解決", [h[0] for h in hits])
        self.assertLess(score, 70)

    def test_二手買賣文不該被當成維修需求(self):
        p = old("女友換新機，這台平常都有貼保護貼包殼，功能一切正常無維修紀錄，售 12000 面交台北。",
                title="[售] iPhone 13 128G 二手出售")
        score, hits = rr.score_post(p, KW)
        self.assertIn("買賣文", [h[0] for h in hits])
        self.assertLess(score, 70)

    def test_開箱評測文要被扣分(self):
        p = old("這次入手的機型效能不錯，跑分我另外貼在下面。散熱表現比上一代好很多，鍵盤手感見仁見智。",
                title="[開箱] 新筆電使用兩週心得分享")
        score, hits = rr.score_post(p, KW)
        self.assertIn("業配廣告", [h[0] for h in hits])
        self.assertLess(score, 70)

    def test_內文太短要扣分(self):
        long_p = old("我的 iPhone 螢幕摔破了想問哪裡修比較好，台北的維修店有推薦的嗎？價格大概多少", "求助")
        short_p = old("iPhone 螢幕破求推薦維修", "求助")
        self.assertIn("內文少於 20 字", [h[0] for h in rr.score_post(short_p, KW)[1]])
        self.assertNotIn("內文少於 20 字", [h[0] for h in rr.score_post(long_p, KW)[1]])

    def test_同作者多篇視為店家推廣(self):
        p = old("iPhone 螢幕維修推薦，本店在台北提供快速換總成服務，摔破可當日取件。", "維修資訊分享", author="shop123")
        normal = rr.score_post(p, KW, {"shop123": 1})[0]
        spammy = rr.score_post(p, KW, {"shop123": 5})[0]
        self.assertEqual(normal - spammy, 25)

    def test_分數夾在0到100之間(self):
        best = old("iPhone 螢幕破摔到進水開不了機求推薦哪裡修，中和維修報價多少錢可寄修", "求救", minutes_ago=1)
        worst = old("已修好了感謝大家，二手出售業配開箱", "已解決")
        self.assertLessEqual(rr.score_post(best, KW)[0], 100)
        self.assertGreaterEqual(rr.score_post(worst, KW)[0], 0)

    def test_關鍵字可自訂(self):
        custom = {"x": {"label": "自訂", "weight": 99, "words": ["藍芽不見"]}}
        p = old("我的耳機藍芽不見了不知道怎麼辦" * 3, "求助")
        self.assertEqual(rr.score_post(p, custom)[0], 99)


class TestQuota(unittest.TestCase):
    def test_額度控管門檻(self):
        self.assertEqual(rr.effective_threshold(0, 70, 200), 70)
        self.assertEqual(rr.effective_threshold(179, 70, 200), 70)
        self.assertEqual(rr.effective_threshold(180, 70, 200), 85)
        self.assertEqual(rr.effective_threshold(194, 70, 200), 85)
        self.assertIsNone(rr.effective_threshold(195, 70, 200))
        self.assertIsNone(rr.effective_threshold(200, 70, 200))


PTT_INDEX_SAMPLE = """
<div class="r-list-container action-bar-margin bbs-screen">
<div class="r-ent">
<div class="nrec"><span class="hl f3">12</span></div>
<div class="mark"></div>
<div class="title">
<a href="/bbs/MobileComm/M.1757000000.A.ABC.html">[問題] iPhone 14 螢幕摔破求推薦</a>
</div>
<div class="meta"><div class="author">kkman0930</div><div class="article-menu"></div><div class="date"> 9/04</div></div>
</div>
<div class="r-ent">
<div class="nrec"></div>
<div class="mark"></div>
<div class="title">
(本文已被刪除) [someone]
</div>
<div class="meta"><div class="author">-</div><div class="article-menu"></div><div class="date"> 9/04</div></div>
</div>
</div>
<a class="btn wide" href="/bbs/MobileComm/index9998.html">&#8249; 上頁</a>
"""

PTT_ARTICLE_SAMPLE = """
<div id="main-content" class="bbs-screen bbs-content">
<div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">kkman0930 (阿凱)</span></div>
<div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">MobileComm</span></div>
<div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[問題] iPhone 14 螢幕摔破求推薦</span></div>
<div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">Thu Sep  4 22:10:33 2026</span></div>
昨天不小心摔到，右上角裂開但還能用，想問台北有沒有推薦的維修店。
<span class="f2">※ 發信站: 批踢踢實業坊(ptt.cc), 來自: 1.2.3.4</span>
<div class="push"><span class="push-tag">推 </span><span class="push-userid">abc</span></div>
</div>
"""


class TestPTTParsing(unittest.TestCase):
    """驗證解析邏輯。真實連線需在自己的電腦上執行 --once 驗證。"""

    def test_索引頁只取得未刪除的文章(self):
        entries = list(rr.ENT_RE.finditer(PTT_INDEX_SAMPLE))
        self.assertEqual(len(entries), 2)
        alive = [m for m in entries if m.group("href")]
        self.assertEqual(len(alive), 1)
        self.assertEqual(rr.strip_tags(alive[0].group("title")),
                         "[問題] iPhone 14 螢幕摔破求推薦")
        self.assertEqual(rr.strip_tags(alive[0].group("author")), "kkman0930")

    def test_找得到上一頁連結(self):
        m = rr.PREV_RE.search(PTT_INDEX_SAMPLE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "/bbs/MobileComm/index9998.html")

    def test_文章時間解析(self):
        iso = rr.parse_ptt_time("Thu Sep  4 22:10:33 2026")
        self.assertIsNotNone(iso)
        self.assertTrue(iso.startswith("2026-09-04T22:10:33"))

    def test_內文擷取不含推文與發信站(self):
        metas = [rr.strip_tags(x) for x in rr.META_RE.findall(PTT_ARTICLE_SAMPLE)]
        self.assertEqual(len(metas), 4)
        body = PTT_ARTICLE_SAMPLE
        cut = __import__("re").search(r'<div id="main-content"[^>]*>', body)
        body = body[cut.end():]
        body = rr.strip_tags(rr.BODY_SPLIT.split(body)[0])
        self.assertIn("右上角裂開", body)
        self.assertNotIn("發信站", body)
        self.assertNotIn("push-userid", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
