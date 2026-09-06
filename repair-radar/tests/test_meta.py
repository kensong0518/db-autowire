# -*- coding: utf-8 -*-
"""Meta 連接器測試：用假的 Graph API 回應驗證解析、去重與過濾。

真實連線未驗證——開發環境的網路政策擋住 graph.facebook.com，
且需要真實的粉專 token。請在自己的電腦上用 --once 實測。
"""
import importlib.util
import os
import unittest
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rr", os.path.join(BASE, "repair_radar.py"))
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

PAGE = "111"
CFG = {
    "meta_page_token": "FAKE",
    "meta_page_id": PAGE,
    "meta_ig_user_id": "222",
    "meta_fetch_messages": True,
    "meta_fetch_comments": True,
    "meta_lookback_hours": 48,
}


def graph_time(minutes_ago):
    dt = datetime.now(rr.TPE) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


class FakeGraph:
    """依 path 尾段回覆固定資料，並記錄呼叫過的路徑。"""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, path, token, params=None):
        self.calls.append(path)
        for suffix, payload in self.table.items():
            if path.endswith(suffix):
                return payload
        return {"data": []}


class MetaTestCase(unittest.TestCase):
    def use(self, table):
        self.fake = FakeGraph(table)
        rr.graph_get = self.fake

    def tearDown(self):
        importlib.reload  # noqa - 保持 rr 模組乾淨由下一個 setUp 覆寫


class TestMetaMessages(MetaTestCase):

    def test_抓到客戶私訊並標記為直達(self):
        self.use({
            "/conversations": {"data": [{"id": "c1", "updated_time": graph_time(10)}]},
            "/messages": {"data": [
                {"id": "m1", "message": "請問 iPhone 14 螢幕摔破換一次多少錢？",
                 "created_time": graph_time(9), "from": {"id": "999", "name": "林小姐"}},
            ]},
        })
        out = rr.crawl_meta(CFG, set())
        dms = [p for p in out if p["direct"]]
        self.assertTrue(dms)
        p = dms[0]
        self.assertIn(p["source"], ("FB 私訊", "IG 私訊"))
        self.assertEqual(p["author"], "林小姐")
        self.assertIn("螢幕摔破", p["body"])
        self.assertTrue(p["id"].startswith("meta_"))

    def test_略過自己回覆的訊息(self):
        self.use({
            "/conversations": {"data": [{"id": "c1", "updated_time": graph_time(5)}]},
            "/messages": {"data": [
                {"id": "mine", "message": "您好，這裡是維修門市",
                 "created_time": graph_time(4), "from": {"id": PAGE, "name": "本店"}},
                {"id": "theirs", "message": "電池膨脹要換嗎",
                 "created_time": graph_time(3), "from": {"id": "999", "name": "客人"}},
            ]},
        })
        ids = [p["id"] for p in rr.crawl_meta(CFG, set())]
        self.assertNotIn("meta_mine", ids)
        self.assertIn("meta_theirs", ids)

    def test_超過回溯時間的訊息不抓(self):
        self.use({
            "/conversations": {"data": [{"id": "c1", "updated_time": graph_time(10)}]},
            "/messages": {"data": [
                {"id": "old", "message": "三天前問過的事",
                 "created_time": graph_time(60 * 72), "from": {"id": "999"}},
            ]},
        })
        self.assertEqual([p for p in rr.crawl_meta(CFG, set()) if p["direct"]], [])

    def test_已處理過的訊息不會重複(self):
        self.use({
            "/conversations": {"data": [{"id": "c1", "updated_time": graph_time(5)}]},
            "/messages": {"data": [
                {"id": "m1", "message": "螢幕破了想問價格",
                 "created_time": graph_time(4), "from": {"id": "999"}},
            ]},
        })
        self.assertEqual(rr.crawl_meta(CFG, {"meta_m1"}), [])


class TestMetaComments(MetaTestCase):

    def test_粉專與IG留言都抓得到且不是直達(self):
        self.use({
            "/feed": {"data": [{"id": "post1", "created_time": graph_time(120),
                                "permalink_url": "https://facebook.com/post1"}]},
            "/media": {"data": [{"id": "ig1", "timestamp": graph_time(180),
                                 "permalink": "https://instagram.com/p/ig1"}]},
            "/comments": {"data": [
                {"id": "cm1", "message": "請問這台泡水還有救嗎",
                 "created_time": graph_time(30), "from": {"name": "路人甲"}},
            ]},
        })
        out = rr.crawl_meta(dict(CFG, meta_fetch_messages=False), set())
        self.assertTrue(out)
        for p in out:
            self.assertEqual(p["direct"], 0)
            self.assertIn(p["source"], ("FB 留言", "IG 留言"))
            self.assertTrue(p["url"].startswith("https://"))

    def test_IG留言用username當作者(self):
        self.use({
            "/media": {"data": [{"id": "ig1", "timestamp": graph_time(60),
                                 "permalink": "https://instagram.com/p/ig1"}]},
            "/comments": {"data": [
                {"id": "c9", "text": "螢幕裂了可以修嗎",
                 "timestamp": graph_time(20), "username": "someone_tw"},
            ]},
        })
        out = rr.crawl_meta(dict(CFG, meta_fetch_messages=False, meta_page_id=""), set())
        self.assertEqual(out[0]["author"], "someone_tw")


class TestMetaSafety(MetaTestCase):

    def test_沒填token就完全不動作(self):
        called = []
        rr.graph_get = lambda *a, **k: called.append(a) or {"data": []}
        self.assertEqual(rr.crawl_meta({"meta_page_token": ""}, set()), [])
        self.assertEqual(called, [])

    def test_API出錯不會讓整輪抓取失敗(self):
        def boom(*a, **k):
            raise RuntimeError("Graph API 190：token 過期")
        rr.graph_get = boom
        self.assertEqual(rr.crawl_meta(CFG, set()), [])

    def test_只打自己帳號的端點(self):
        self.use({"/conversations": {"data": []}, "/feed": {"data": []}, "/media": {"data": []}})
        rr.crawl_meta(CFG, set())
        for path in self.fake.calls:
            self.assertTrue(path.startswith((PAGE, "222")),
                            "不該存取自己帳號以外的端點：%s" % path)

    def test_時間格式轉換(self):
        iso = rr.meta_time("2026-09-05T10:00:00+0000")
        self.assertIsNotNone(iso)
        self.assertTrue(iso.startswith("2026-09-05T18:00:00"), iso)  # UTC+8


class TestDirectNotification(unittest.TestCase):

    def test_私訊通知標題不同(self):
        dm = {"title": "螢幕破多少錢", "source": "IG 私訊", "body": "想問一下",
              "posted_at": graph_time(2), "direct": 1, "url": "https://x"}
        post = dict(dm, direct=0, source="PTT MobileComm")
        self.assertIn("有人私訊你", rr.format_notification(dm, 40))
        self.assertIn("新維修需求", rr.format_notification(post, 80))


if __name__ == "__main__":
    unittest.main(verbosity=2)
