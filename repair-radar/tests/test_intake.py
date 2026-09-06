# -*- coding: utf-8 -*-
"""v2 收機檢查、照片、客戶歷史、保固、資料庫升級的單元測試"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rr", os.path.join(BASE, "repair_radar.py"))
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

TINY_PNG = ("data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class TestPhotoSafety(unittest.TestCase):
    """檔名白名單是防路徑穿越的第一道門，必須擋死。"""

    def test_合法檔名放行(self):
        for n in ("a1b2_20260906_ab12.jpg", "o1_1.png", "x-y.webp", "A.jpeg"):
            self.assertEqual(rr.safe_photo_name(n), n, n)

    def test_路徑穿越一律擋掉(self):
        for bad in ("../data.db", "..\\data.db", "a/b.jpg", "/etc/passwd",
                    "....//x.jpg", "./x.jpg", "x/../../y.jpg"):
            self.assertIsNone(rr.safe_photo_name(bad), bad)

    def test_非圖片副檔名擋掉(self):
        for bad in ("repair_radar.py", "data.db", "x.sh", "x", "x.jpg.py"):
            self.assertIsNone(rr.safe_photo_name(bad), bad)

    def test_空值與超長檔名擋掉(self):
        self.assertIsNone(rr.safe_photo_name(""))
        self.assertIsNone(rr.safe_photo_name(None))
        self.assertIsNone(rr.safe_photo_name("a" * 200 + ".jpg"))

    def test_奇怪字元擋掉(self):
        for bad in ("a b.jpg", "a;b.jpg", "a$b.jpg", "中文.jpg", "a\x00.jpg"):
            self.assertIsNone(rr.safe_photo_name(bad), bad)


class TestPhotoSave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig, rr.PHOTO_DIR = rr.PHOTO_DIR, self.tmp

    def tearDown(self):
        rr.PHOTO_DIR = self.orig

    def test_寫成實體檔案而不是塞進資料庫(self):
        name, size = rr.save_photo("o123", TINY_PNG)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, name)))
        self.assertGreater(size, 0)
        self.assertEqual(rr.safe_photo_name(name), name, "產生的檔名自己要過白名單")
        self.assertTrue(name.startswith("o123_"))

    def test_工單id被消毒過(self):
        name, _ = rr.save_photo("../../etc", TINY_PNG)
        self.assertEqual(rr.safe_photo_name(name), name)
        self.assertNotIn("..", name)
        self.assertNotIn("/", name)

    def test_非圖片內容被拒絕(self):
        for bad in ("", "hello", "data:text/plain;base64,aGk=", "data:image/gif;base64,aGk="):
            with self.assertRaises(ValueError):
                rr.save_photo("o1", bad)

    def test_刪工單一併刪照片(self):
        n1, _ = rr.save_photo("o1", TINY_PNG)
        n2, _ = rr.save_photo("o1", TINY_PNG)
        self.assertEqual(rr.delete_photos('["%s","%s"]' % (n1, n2)), 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, n1)))

    def test_刪照片時的惡意檔名不會碰到別的檔(self):
        keep = os.path.join(self.tmp, "keep.txt")
        with open(keep, "w") as f:
            f.write("x")
        rr.delete_photos('["../keep.txt", "/etc/passwd", "keep.txt"]')
        self.assertTrue(os.path.exists(keep), "keep.txt 副檔名不在白名單，不該被刪")


class TestPhone(unittest.TestCase):
    def test_各種寫法都正規化成同一組(self):
        for v in ("0912345678", "0912-345-678", "0912 345 678",
                  "+886912345678", "886912345678", "(0912)345678"):
            self.assertEqual(rr.normalize_phone(v), "0912345678", v)

    def test_空值不會爆(self):
        self.assertEqual(rr.normalize_phone(None), "")
        self.assertEqual(rr.normalize_phone(""), "")


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp(suffix=".db")
        self.orig, rr.DB_PATH = rr.DB_PATH, self.path
        rr.init_db()
        with rr.db() as conn:
            for i, (oid, phone, dev) in enumerate([
                ("a", "0912345678", "iPhone 13"),
                ("b", "0912-345-678", "iPad Air"),
                ("c", "0999888777", "Pixel"),
            ]):
                rr.upsert(conn, "orders", rr.ORDER_COLS, {
                    "id": oid, "no": "R-%d" % i, "customer": "客", "phone": phone,
                    "device": dev, "status": "done",
                    "created_at": (datetime.now(rr.TPE) - timedelta(days=i)).isoformat()})

    def tearDown(self):
        rr.DB_PATH = self.orig
        os.close(self.fd)
        os.unlink(self.path)

    def test_不同寫法的同一支電話會被算在一起(self):
        with rr.db() as conn:
            rows = rr.phone_history(conn, "+886912345678")
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["device"] for r in rows}, {"iPhone 13", "iPad Air"})

    def test_可排除正在編輯的那張單(self):
        with rr.db() as conn:
            rows = rr.phone_history(conn, "0912345678", exclude_id="a")
        self.assertEqual([r["id"] for r in rows], ["b"])

    def test_太短的號碼不查(self):
        with rr.db() as conn:
            self.assertEqual(rr.phone_history(conn, "0912"), [])


class TestWarranty(unittest.TestCase):
    def test_預設九十天(self):
        until = datetime.fromisoformat(rr.warranty_until(90))
        self.assertEqual((until.date() - datetime.now(rr.TPE).date()).days, 90)

    def test_泡水機可設短保固(self):
        until = datetime.fromisoformat(rr.warranty_until(7))
        self.assertEqual((until.date() - datetime.now(rr.TPE).date()).days, 7)


class TestMigration(unittest.TestCase):
    """舊使用者的 data.db 必須無痛升級，不能要求刪檔重建。"""

    def setUp(self):
        self.fd, self.path = tempfile.mkstemp(suffix=".db")
        self.orig, rr.DB_PATH = rr.DB_PATH, self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
        CREATE TABLE posts (id TEXT PRIMARY KEY, title TEXT, body TEXT, source TEXT,
          board TEXT, author TEXT, url TEXT UNIQUE, posted_at TEXT, score INTEGER,
          status TEXT, notified INTEGER, created_at TEXT);
        CREATE TABLE orders (id TEXT PRIMARY KEY, no TEXT, customer TEXT, phone TEXT,
          device TEXT, symptom TEXT, quote INTEGER, paid INTEGER, source TEXT,
          status TEXT, note TEXT, lead_url TEXT, created_at TEXT, due_at TEXT);
        CREATE TABLE settings (k TEXT PRIMARY KEY, v TEXT);
        """)
        conn.execute("INSERT INTO orders(id,no,customer,quote,status) "
                     "VALUES('old','R-OLD','舊客戶',3000,'done')")
        conn.commit()
        conn.close()

    def tearDown(self):
        rr.DB_PATH = self.orig
        os.close(self.fd)
        os.unlink(self.path)

    def test_舊資料庫升級後欄位齊全且資料還在(self):
        rr.init_db()
        with rr.db() as conn:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(orders)")}
            for col, _ in rr.ORDER_NEW_COLS:
                self.assertIn(col, cols, col)
            row = conn.execute("SELECT * FROM orders WHERE id='old'").fetchone()
            self.assertEqual(row["customer"], "舊客戶")
            self.assertEqual(row["quote"], 3000)
            self.assertEqual(row["warranty_days"], 90, "新欄位要有預設值")
            self.assertTrue(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='parts'").fetchone())

    def test_升級可重複執行(self):
        rr.init_db()
        rr.init_db()
        with rr.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
