#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
維修接單台 — 單機版
============================================================
一個檔案跑起整套：PTT 爬蟲 + 意圖評分 + 本機網頁伺服器 + LINE/Telegram 推播。

啟動：
    python3 repair_radar.py
然後瀏覽器會自動打開 http://127.0.0.1:8420

只用 Python 標準函式庫，不需要 pip install 任何東西。
"""

import argparse
import html
import http.server
import json
import os
import re
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
DB_PATH = os.path.join(BASE_DIR, "data.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CONFIG_EXAMPLE = os.path.join(BASE_DIR, "config.example.json")
KEYWORDS_PATH = os.path.join(BASE_DIR, "keywords.json")

TPE = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

LOCK = threading.Lock()

PAGE_SHELL = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b1113">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#128295;</text></svg>">
<style>img{max-width:100%%}[hidden]{display:none!important}</style>
%s
</html>
"""




# ============================================================
# 設定
# ============================================================
DEFAULT_CONFIG = {
    "_說明": "填好 token 後這個檔案就有你的金鑰，不要傳給別人也不要上傳 GitHub。留空代表關閉該功能。",
    "ptt_boards": ["MobileComm", "iOS", "Android", "nb-shopping",
                   "NewTaipei", "Kaohsiung", "TaichungBun"],
    "ptt_pages": 2,
    "crawl_interval_minutes": 10,
    "line_channel_token": "",
    "line_user_id": "",
    "line_monthly_quota": 200,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notify_threshold": 70,
    "port": 8420,

    "_meta說明": ("接自己的粉專與 IG 商業帳號，抓自家的私訊與留言。"
                  "這是 Meta 官方支援的方式，不是爬別人的社團或 Marketplace——"
                  "那種做法會讓帳號被停權，本程式不做。留空即關閉。"),
    "meta_page_token": "",
    "meta_page_id": "",
    "meta_ig_user_id": "",
    "meta_fetch_messages": True,
    "meta_fetch_comments": True,
    "meta_lookback_hours": 48,
}

DEFAULT_KEYWORDS = {
    "intent": {"label": "求助意圖", "weight": 30, "words": [
        "求推薦", "有推薦嗎", "推薦嗎", "有沒有推薦", "有推薦", "推薦的",
        "有人推薦", "板友推薦", "求救", "求助", "哪裡修", "哪邊修", "去哪修",
        "該修還是換", "有人知道", "跪求", "請問有", "想問", "請問", "求問",
        "怎麼辦", "怎麼處理"]},
    "fault": {"label": "故障描述", "weight": 25, "words": [
        "螢幕破", "螢幕裂", "螢幕摔", "摔到", "摔破", "進水", "泡水", "開不了機",
        "無法開機", "充不了電", "不能充電", "電池膨脹", "耗電快", "鏡頭裂",
        "面板", "觸控失靈", "失靈", "主機板", "黑屏", "沒畫面", "尾插", "充電孔"]},
    "device": {"label": "裝置型號", "weight": 15, "words": [
        "iPhone", "iPad", "Android", "Samsung", "三星", "Pixel", "Switch",
        "MacBook", "筆電", "平板", "華碩", "ASUS", "小米", "OPPO", "Sony",
        "ROG", "紅米", "vivo", "realme"]},
    "repair": {"label": "維修字眼", "weight": 15, "words": [
        "維修", "修理", "送修", "報價", "價格", "多少錢", "估價", "換螢幕", "換電池"]},
    "region": {"label": "雙北地區", "weight": 10, "words": [
        "台北", "臺北", "新北", "中和", "永和", "板橋", "南勢角", "景安",
        "雙北", "新店", "土城"]},
    "mail": {"label": "可寄修", "weight": 5, "words": ["寄修", "可寄", "宅配"]},
    "done": {"label": "已解決", "weight": -40, "words": [
        "已修好", "修好了", "修完", "感謝大家", "已解決", "結案", "已處理完"]},
    "trade": {"label": "買賣文", "weight": -30, "words": [
        "二手", "出售", "徵求購買", "收購", "換現金", "讓售", "便宜賣"]},
    "ad": {"label": "業配廣告", "weight": -25, "words": [
        "業配", "廣告", "開箱", "評測", "實測心得", "合作文"]},
}


def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return json.loads(json.dumps(default))
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log("讀取 %s 失敗（%s），改用預設值" % (os.path.basename(path), e))
        return json.loads(json.dumps(default))
    merged = json.loads(json.dumps(default))
    merged.update(data)
    return merged


def log(msg):
    print("[%s] %s" % (datetime.now(TPE).strftime("%H:%M:%S"), msg), flush=True)


# ============================================================
# 資料庫
# ============================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY,
  title TEXT, body TEXT, source TEXT, board TEXT,
  author TEXT, url TEXT UNIQUE, posted_at TEXT,
  score INTEGER DEFAULT 0, status TEXT DEFAULT 'new',
  notified INTEGER DEFAULT 0, direct INTEGER DEFAULT 0, created_at TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  no TEXT, customer TEXT, phone TEXT, device TEXT, symptom TEXT,
  quote INTEGER DEFAULT 0, paid INTEGER DEFAULT 0,
  source TEXT, status TEXT DEFAULT 'intake', note TEXT,
  lead_url TEXT, created_at TEXT, due_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS idx_posts_time ON posts(posted_at DESC);
"""

POST_COLS = ["id", "title", "body", "source", "board", "author", "url",
             "posted_at", "score", "status", "notified", "direct", "created_at"]
ORDER_COLS = ["id", "no", "customer", "phone", "device", "symptom", "quote",
              "paid", "source", "status", "note", "lead_url", "created_at", "due_at"]


def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        # 舊版資料庫升級：補上後來才加的欄位
        have = {r["name"] for r in conn.execute("PRAGMA table_info(posts)")}
        if "direct" not in have:
            conn.execute("ALTER TABLE posts ADD COLUMN direct INTEGER DEFAULT 0")
            log("資料庫已升級：posts 新增 direct 欄位")


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT v FROM settings WHERE k=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["v"])
    except Exception:
        return row["v"]


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(k,v) VALUES(?,?) "
                 "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                 (key, json.dumps(value, ensure_ascii=False)))


def upsert(conn, table, cols, rec):
    fields = [c for c in cols if c in rec]
    placeholders = ",".join("?" for _ in fields)
    updates = ",".join("%s=excluded.%s" % (c, c) for c in fields if c != "id")
    sql = "INSERT INTO %s(%s) VALUES(%s) ON CONFLICT(id) DO UPDATE SET %s" % (
        table, ",".join(fields), placeholders, updates or "id=id")
    conn.execute(sql, [rec[c] for c in fields])


# ============================================================
# 意圖評分（與網頁前端規則一致）
# ============================================================
RULE_FRESH = ("60 分鐘內新文", 10)
RULE_SHORT = ("內文少於 20 字", -15)
RULE_SHOP = ("疑似店家推廣（同作者多篇）", -25)


def score_post(post, keywords, author_counts=None):
    text = ((post.get("title") or "") + "\n" + (post.get("body") or "")).lower()
    total, hits = 0, []

    for group in keywords.values():
        found = [w for w in group.get("words", []) if w and w.lower() in text]
        if found:
            total += group["weight"]
            hits.append((group["label"], group["weight"], "、".join(found[:3])))

    age_min = age_minutes(post.get("posted_at"))
    if age_min is not None and age_min <= 60:
        total += RULE_FRESH[1]
        hits.append((RULE_FRESH[0], RULE_FRESH[1], "%d 分鐘前" % max(0, int(age_min))))

    body_len = len(re.sub(r"\s", "", post.get("body") or ""))
    if body_len < 20:
        total += RULE_SHORT[1]
        hits.append((RULE_SHORT[0], RULE_SHORT[1], "%d 字" % body_len))

    author = post.get("author") or ""
    if author and author_counts and author_counts.get(author, 0) >= 3:
        total += RULE_SHOP[1]
        hits.append((RULE_SHOP[0], RULE_SHOP[1], "%d 篇" % author_counts[author]))

    return max(0, min(100, total)), hits


def age_minutes(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TPE)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60
    except Exception:
        return None


# ============================================================
# PTT 爬蟲
# ============================================================
def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Cookie": "over18=1",
        "Accept-Language": "zh-TW,zh;q=0.9",
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
    return raw.decode("utf-8", errors="replace")


ENT_RE = re.compile(
    r'<div class="r-ent">.*?<div class="nrec">(?P<nrec>.*?)</div>.*?'
    r'<div class="title">\s*(?:<a href="(?P<href>[^"]+)">(?P<title>.*?)</a>)?.*?</div>.*?'
    r'<div class="author">(?P<author>.*?)</div>.*?'
    r'<div class="date">(?P<date>.*?)</div>',
    re.S)
PREV_RE = re.compile(r'<a class="btn wide" href="([^"]+)">&#8249;\s*上頁</a>')
META_RE = re.compile(r'<span class="article-meta-value">(.*?)</span>', re.S)
BODY_SPLIT = re.compile(r'※\s*發信站|<span class="f2">※')


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def parse_ptt_time(s):
    """PTT 文章時間：'Thu Sep  4 22:10:33 2025'"""
    for fmt in ("%a %b %d %H:%M:%S %Y", "%a %b  %d %H:%M:%S %Y"):
        try:
            dt = datetime.strptime(" ".join(s.split()), " ".join(fmt.split()))
            return dt.replace(tzinfo=TPE).isoformat()
        except Exception:
            continue
    return None


def crawl_ptt_board(board, pages, known_urls, delay=0.4):
    """回傳這個看板的新貼文清單。任何一步失敗只影響這個看板。"""
    out = []
    index_url = "https://www.ptt.cc/bbs/%s/index.html" % board
    for _ in range(max(1, pages)):
        try:
            page = fetch(index_url)
        except Exception as e:
            log("  %s 索引頁抓取失敗：%s" % (board, e))
            break

        for m in ENT_RE.finditer(page):
            href = m.group("href")
            if not href:          # 已刪除的文章
                continue
            url = "https://www.ptt.cc" + href
            if url in known_urls:
                continue
            title = strip_tags(m.group("title"))
            author = strip_tags(m.group("author"))
            if author in ("-", ""):
                continue
            try:
                time.sleep(delay)
                article = fetch(url)
            except Exception as e:
                log("  %s 內文抓取失敗：%s" % (href, e))
                continue

            metas = [strip_tags(x) for x in META_RE.findall(article)]
            posted = parse_ptt_time(metas[3]) if len(metas) >= 4 else None

            body = article
            cut = re.search(r'<div id="main-content"[^>]*>', body)
            if cut:
                body = body[cut.end():]
            parts = BODY_SPLIT.split(body)
            body = strip_tags(parts[0])
            # 去掉開頭的 meta 行
            body = re.sub(r"^.*?時間.*?\d{4}\s*", "", body, count=1, flags=re.S)

            out.append({
                "id": href.strip("/").replace("/", "_"),
                "title": title,
                "body": body[:2000],
                "source": "PTT %s" % board,
                "board": board,
                "author": author,
                "url": url,
                "posted_at": posted or datetime.now(TPE).isoformat(),
            })
            known_urls.add(url)

        prev = PREV_RE.search(page)
        if not prev:
            break
        index_url = "https://www.ptt.cc" + prev.group(1)
    return out



# ============================================================
# Meta 連接器：自己的粉專與 IG 商業帳號
# ------------------------------------------------------------
# 只讀取「你自己擁有的」粉專／IG 帳號的私訊與留言，走 Meta 官方
# Graph API。不登入他人帳號、不碰社團、不碰 Marketplace——那些做法
# 違反使用條款且會導致帳號停權。
# ============================================================
GRAPH = "https://graph.facebook.com/v21.0"


def graph_get(path, token, params=None):
    q = dict(params or {})
    q["access_token"] = token
    url = "%s/%s?%s" % (GRAPH, path.lstrip("/"), urllib.parse.urlencode(q))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20,
                                    context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError("Graph API %s：%s" % (e.code, detail))


def meta_time(s):
    """Graph API 時間格式：2026-09-05T10:00:00+0000"""
    if not s:
        return None
    try:
        cleaned = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
        return datetime.fromisoformat(cleaned).astimezone(TPE).isoformat()
    except Exception:
        return None


def _within(iso, hours):
    age = age_minutes(iso)
    return age is None or age <= hours * 60


def _lead(kind, ident, author, text, url, posted_at, direct):
    text = re.sub(r"\s+", " ", text or "").strip()
    return {
        "id": "meta_%s" % ident,
        "title": text[:40] + ("…" if len(text) > 40 else ""),
        "body": text,
        "source": kind,
        "board": "meta",
        "author": author or "（未提供名稱）",
        "url": url or "",
        "posted_at": posted_at or datetime.now(TPE).isoformat(),
        "direct": 1 if direct else 0,
    }


def crawl_meta_messages(cfg, known, out):
    """粉專與 IG 的私訊。收件匣裡的訊息本來就是找上門的客人。"""
    token, page = cfg["meta_page_token"], cfg.get("meta_page_id")
    hours = int(cfg.get("meta_lookback_hours", 48))
    if not page:
        return
    for platform, label in (("messenger", "FB 私訊"), ("instagram", "IG 私訊")):
        try:
            convos = graph_get("%s/conversations" % page, token, {
                "platform": platform, "fields": "id,updated_time", "limit": 25})
        except Exception as e:
            log("  %s 讀取失敗：%s" % (label, e))
            continue
        for c in convos.get("data", []):
            if not _within(meta_time(c.get("updated_time")), hours):
                continue
            try:
                msgs = graph_get("%s/messages" % c["id"], token, {
                    "fields": "id,message,created_time,from", "limit": 15})
            except Exception as e:
                log("  %s 對話讀取失敗：%s" % (label, e))
                continue
            for m in msgs.get("data", []):
                sender = (m.get("from") or {}).get("id", "")
                # 略過自己回的訊息
                if sender and page and str(sender) == str(page):
                    continue
                text = m.get("message")
                posted = meta_time(m.get("created_time"))
                if not text or not _within(posted, hours):
                    continue
                if "meta_%s" % m["id"] in known:
                    continue
                out.append(_lead(label, m["id"],
                                 (m.get("from") or {}).get("name"), text,
                                 "https://business.facebook.com/latest/inbox",
                                 posted, direct=True))
                known.add("meta_%s" % m["id"])


def crawl_meta_comments(cfg, known, out):
    """粉專貼文與 IG 貼文底下的留言。"""
    token = cfg["meta_page_token"]
    hours = int(cfg.get("meta_lookback_hours", 48))

    targets = []
    if cfg.get("meta_page_id"):
        targets.append(("FB 留言", "%s/feed" % cfg["meta_page_id"],
                        "id,permalink_url,created_time"))
    if cfg.get("meta_ig_user_id"):
        targets.append(("IG 留言", "%s/media" % cfg["meta_ig_user_id"],
                        "id,permalink,timestamp"))

    for label, path, fields in targets:
        try:
            items = graph_get(path, token, {"fields": fields, "limit": 15})
        except Exception as e:
            log("  %s 讀取失敗：%s" % (label, e))
            continue
        for item in items.get("data", []):
            when = meta_time(item.get("created_time") or item.get("timestamp"))
            if not _within(when, hours * 4):     # 舊貼文也可能有新留言
                continue
            link = item.get("permalink_url") or item.get("permalink") or ""
            try:
                comments = graph_get("%s/comments" % item["id"], token, {
                    "fields": "id,text,message,username,from,timestamp,created_time",
                    "limit": 30})
            except Exception as e:
                log("  %s 留言讀取失敗：%s" % (label, e))
                continue
            for c in comments.get("data", []):
                text = c.get("message") or c.get("text")
                posted = meta_time(c.get("created_time") or c.get("timestamp"))
                if not text or not _within(posted, hours):
                    continue
                if "meta_%s" % c["id"] in known:
                    continue
                author = c.get("username") or (c.get("from") or {}).get("name")
                out.append(_lead(label, c["id"], author, text, link,
                                 posted, direct=False))
                known.add("meta_%s" % c["id"])


def crawl_meta(cfg, known):
    """回傳粉專／IG 的新線索。整段失敗只記錄，不影響 PTT。"""
    if not cfg.get("meta_page_token"):
        return []
    out = []
    try:
        if cfg.get("meta_fetch_messages", True):
            crawl_meta_messages(cfg, known, out)
        if cfg.get("meta_fetch_comments", True):
            crawl_meta_comments(cfg, known, out)
    except Exception as e:
        log("  Meta 連接器整段失敗，略過：%s" % e)
    return out


# ============================================================
# 通知
# ============================================================
def post_json(url, payload, headers=None, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "User-Agent": UA}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout,
                                context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", errors="replace")


def format_notification(post, score):
    body = re.sub(r"\s+", " ", post.get("body") or "")[:90]
    age = age_minutes(post.get("posted_at"))
    when = "%d 分鐘前" % int(age) if age is not None and age < 1440 else "稍早"
    head = "📩 有人私訊你" if post.get("direct") else "🔧 新維修需求（%d 分）" % score
    return ("%s\n\n【%s】\n來源：%s\n時間：%s\n摘要：%s…\n\n👉 %s"
            % (head, post.get("title", ""), post.get("source", ""),
               when, body, post.get("url", "")))


def send_line(cfg, text):
    if not cfg.get("line_channel_token") or not cfg.get("line_user_id"):
        return False, "未設定"
    try:
        post_json("https://api.line.me/v2/bot/message/push",
                  {"to": cfg["line_user_id"],
                   "messages": [{"type": "text", "text": text[:4900]}]},
                  {"Authorization": "Bearer " + cfg["line_channel_token"]})
        return True, "ok"
    except Exception as e:
        return False, str(e)


def send_telegram(cfg, text):
    if not cfg.get("telegram_bot_token") or not cfg.get("telegram_chat_id"):
        return False, "未設定"
    try:
        post_json("https://api.telegram.org/bot%s/sendMessage" % cfg["telegram_bot_token"],
                  {"chat_id": cfg["telegram_chat_id"],
                   "text": text[:4000],
                   "disable_web_page_preview": False})
        return True, "ok"
    except Exception as e:
        return False, str(e)


def month_key():
    return datetime.now(TPE).strftime("%Y-%m")


def effective_threshold(used, base, quota):
    """額度控管：已用 >= quota-20 提高到 85；>= quota-5 停止 LINE。"""
    if used >= quota - 5:
        return None            # 停推 LINE
    if used >= quota - 20:
        return max(base, 85)
    return base


# ============================================================
# 爬蟲主流程
# ============================================================
def run_crawl(cfg, keywords):
    started = time.time()
    with db() as conn:
        known = {r["url"] for r in conn.execute("SELECT url FROM posts")}
        author_counts = {r["author"]: r["n"] for r in conn.execute(
            "SELECT author, COUNT(*) n FROM posts GROUP BY author")}

    fresh = []
    for board in cfg.get("ptt_boards", []):
        try:
            got = crawl_ptt_board(board, cfg.get("ptt_pages", 2), known)
            log("  %s：新增 %d 則" % (board, len(got)))
            fresh.extend(got)
        except Exception as e:
            log("  %s 整版失敗，略過：%s" % (board, e))

    if cfg.get("meta_page_token"):
        with db() as conn:
            known_ids = {r["id"] for r in conn.execute("SELECT id FROM posts")}
        meta_leads = crawl_meta(cfg, known_ids)
        if meta_leads:
            log("  粉專／IG：新增 %d 則（其中私訊 %d 則）"
                % (len(meta_leads), sum(x["direct"] for x in meta_leads)))
        fresh.extend(meta_leads)

    notified = 0
    with LOCK, db() as conn:
        used = int(get_setting(conn, "line_quota_used", 0) or 0)
        if get_setting(conn, "quota_month") != month_key():
            used = 0
            set_setting(conn, "quota_month", month_key())
        quota = int(cfg.get("line_monthly_quota", 200))
        base = int(cfg.get("notify_threshold", 70))

        for p in fresh:
            author_counts[p["author"]] = author_counts.get(p["author"], 0) + 1
            score, _ = score_post(p, keywords, author_counts)
            p["score"] = score
            p["status"] = "new"
            p["notified"] = 0
            p.setdefault("direct", 0)
            p["created_at"] = datetime.now(TPE).isoformat()
            upsert(conn, "posts", POST_COLS, p)

            text = format_notification(p, score)
            # Telegram 免費無上限：全部推
            send_telegram(cfg, text)

            thr = effective_threshold(used, base, quota)
            # 自家粉專／IG 的私訊是找上門的客人，不受分數門檻擋
            if thr is not None and (score >= thr or p.get("direct")):
                ok, err = send_line(cfg, text)
                if ok:
                    used += 1
                    notified += 1
                    conn.execute("UPDATE posts SET notified=1 WHERE id=?", (p["id"],))
                elif err != "未設定":
                    log("  LINE 推播失敗：%s" % err)

        set_setting(conn, "line_quota_used", used)
        set_setting(conn, "last_crawl", datetime.now(TPE).isoformat())
        set_setting(conn, "last_crawl_new", len(fresh))

    log("抓取完成：新增 %d 則，LINE 推播 %d 則，耗時 %.1f 秒"
        % (len(fresh), notified, time.time() - started))
    return len(fresh)


def crawl_loop(cfg, keywords, stop_event):
    interval = max(1, int(cfg.get("crawl_interval_minutes", 10))) * 60
    while not stop_event.is_set():
        try:
            log("開始抓取 PTT…")
            run_crawl(cfg, keywords)
        except Exception as e:
            log("抓取發生未預期錯誤（已忽略，下一輪會再試）：%s" % e)
        stop_event.wait(interval)


# ============================================================
# 網頁伺服器
# ============================================================
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "RepairRadar"
    cfg = {}
    keywords = {}

    def log_message(self, *_):
        pass

    # ---------- helpers ----------
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def serve_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404, "not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_page(self):
        """web/index.html 只有頁面內容，這裡補上 doctype 與 head。"""
        try:
            with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as f:
                content = f.read()
        except OSError:
            self.send_error(404, "找不到 web/index.html")
            return
        if not content.lstrip().lower().startswith("<!doctype"):
            content = PAGE_SHELL % content
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---------- routes ----------
    def do_GET(self):
        route = urllib.parse.urlparse(self.path).path
        if route in ("/", "/index.html"):
            return self.serve_page()
        if route == "/api/state":
            return self.send_json(self.state())
        if route == "/api/keywords":
            return self.send_json(Handler.keywords)
        if route == "/api/crawl-now":
            threading.Thread(target=run_crawl,
                             args=(Handler.cfg, Handler.keywords),
                             daemon=True).start()
            return self.send_json({"ok": True, "msg": "已開始抓取"})
        self.send_error(404, "not found")

    def do_POST(self):
        route = urllib.parse.urlparse(self.path).path
        payload = self.read_json()
        try:
            with LOCK, db() as conn:
                if route == "/api/orders":
                    rec = {k: payload.get(k) for k in ORDER_COLS if k in payload}
                    if not rec.get("id"):
                        return self.send_json({"ok": False, "msg": "缺少 id"}, 400)
                    upsert(conn, "orders", ORDER_COLS, rec)
                elif route == "/api/posts":
                    rec = {k: payload.get(k) for k in POST_COLS if k in payload}
                    if not rec.get("id"):
                        return self.send_json({"ok": False, "msg": "缺少 id"}, 400)
                    if "score" not in rec or rec.get("score") is None:
                        rec["score"] = score_post(rec, Handler.keywords)[0]
                    upsert(conn, "posts", POST_COLS, rec)
                elif route == "/api/delete":
                    table = payload.get("table")
                    if table not in ("orders", "posts"):
                        return self.send_json({"ok": False, "msg": "table 不合法"}, 400)
                    conn.execute("DELETE FROM %s WHERE id=?" % table,
                                 (payload.get("id"),))
                elif route == "/api/settings":
                    for k, v in payload.items():
                        set_setting(conn, k, v)
                elif route == "/api/keywords":
                    kws = payload if isinstance(payload, dict) and payload else DEFAULT_KEYWORDS
                    Handler.keywords = kws
                    with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
                        json.dump(kws, f, ensure_ascii=False, indent=2)
                    self.rescore(conn)
                else:
                    return self.send_error(404, "not found")
            return self.send_json({"ok": True})
        except Exception as e:
            return self.send_json({"ok": False, "msg": str(e)}, 500)

    def rescore(self, conn):
        counts = {r["author"]: r["n"] for r in conn.execute(
            "SELECT author, COUNT(*) n FROM posts GROUP BY author")}
        for row in conn.execute("SELECT * FROM posts").fetchall():
            p = dict(row)
            conn.execute("UPDATE posts SET score=? WHERE id=?",
                         (score_post(p, Handler.keywords, counts)[0], p["id"]))

    def state(self):
        with db() as conn:
            posts = [dict(r) for r in conn.execute(
                "SELECT * FROM posts ORDER BY posted_at DESC LIMIT 400")]
            orders = [dict(r) for r in conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT 400")]
            settings = {r["k"]: json.loads(r["v"]) for r in
                        conn.execute("SELECT k,v FROM settings")}
        settings.setdefault("line_quota_used", 0)
        settings["line_monthly_quota"] = Handler.cfg.get("line_monthly_quota", 200)
        settings["notify_threshold"] = Handler.cfg.get("notify_threshold", 70)
        settings["line_ready"] = bool(Handler.cfg.get("line_channel_token"))
        settings["telegram_ready"] = bool(Handler.cfg.get("telegram_bot_token"))
        settings["meta_ready"] = bool(Handler.cfg.get("meta_page_token"))
        settings["meta_page_ready"] = bool(Handler.cfg.get("meta_page_id"))
        settings["meta_ig_ready"] = bool(Handler.cfg.get("meta_ig_user_id"))
        settings["crawl_interval_minutes"] = Handler.cfg.get("crawl_interval_minutes", 10)
        settings["boards"] = Handler.cfg.get("ptt_boards", [])
        return {"posts": posts, "orders": orders,
                "settings": settings, "keywords": Handler.keywords}


class ThreadedServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ============================================================
# main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="維修接單台 — 單機版")
    parser.add_argument("--port", type=int, help="網頁埠號")
    parser.add_argument("--once", action="store_true", help="只跑一次爬蟲就結束，不開網頁")
    parser.add_argument("--no-crawl", action="store_true", help="只開網頁，不跑爬蟲")
    parser.add_argument("--no-browser", action="store_true", help="不要自動打開瀏覽器")
    args = parser.parse_args()

    if not os.path.exists(CONFIG_PATH) and os.path.exists(CONFIG_EXAMPLE):
        with open(CONFIG_EXAMPLE, encoding="utf-8") as src, \
             open(CONFIG_PATH, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        log("已建立 config.json，填入 LINE / Telegram token 就會開始推播")

    cfg = load_json(CONFIG_PATH, DEFAULT_CONFIG)
    keywords = load_json(KEYWORDS_PATH, DEFAULT_KEYWORDS)
    init_db()

    if args.once:
        run_crawl(cfg, keywords)
        return

    Handler.cfg = cfg
    Handler.keywords = keywords
    port = args.port or int(cfg.get("port", 8420))

    stop_event = threading.Event()
    if not args.no_crawl:
        threading.Thread(target=crawl_loop, args=(cfg, keywords, stop_event),
                         daemon=True).start()

    try:
        httpd = ThreadedServer(("127.0.0.1", port), Handler)
    except OSError as e:
        log("埠號 %d 被占用（%s）。換一個：python3 repair_radar.py --port 8421" % (port, e))
        sys.exit(1)

    url = "http://127.0.0.1:%d" % port
    log("=" * 52)
    log("維修接單台已啟動：%s" % url)
    log("關掉這個視窗就會停止。資料存在 data.db")
    log("LINE 推播：%s　Telegram 推播：%s"
        % ("已設定" if cfg.get("line_channel_token") else "未設定",
           "已設定" if cfg.get("telegram_bot_token") else "未設定"))
    log("=" * 52)

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("收到中斷，正在關閉…")
    finally:
        stop_event.set()
        httpd.server_close()


if __name__ == "__main__":
    main()
