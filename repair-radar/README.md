# 維修需求雷達 — 網頁看板（web/）

自動抓取跑在 GitHub Actions；這個資料夾是**看板前端**。

## 為什麼網頁抓不到 PTT

瀏覽器有同源政策，PTT / Dcard 都沒有開放 CORS，前端 `fetch` 一定被擋。
爬蟲必須跑在伺服器端（GitHub Actions cron），把結果寫進資料庫或輸出 JSON，
再由看板讀取。這是規格中架構圖的原設計，不是妥協。

## 這個頁面能做什麼

| 功能 | 說明 |
|---|---|
| 意圖評分 | 完整實作規格第五節的加減分規則，0~100 分 |
| 分數拆解 | 每則按「分數怎麼算」可看命中哪些關鍵字、各加減幾分 |
| 關鍵字自訂 | 右上「關鍵字」可直接改各組關鍵字，存檔後全部貼文即時重算 |
| LINE 額度控管 | 已用 ≥180 門檻升到 85、≥195 停推並在頂端顯示警示 |
| 三段式看板 | 現在該回 / 其餘需求 / 已處理（已處理自動沉底） |
| 篩選 | 狀態、來源、裝置與故障類型、分數區間、時間範圍、關鍵字搜尋 |
| 狀態追蹤 | 未處理 / 已聯絡 / 已成交 / 不適合，寫入 Artifact db，換裝置同步 |
| 話術生成 | 依裝置 + 故障類型 + 地區組模板，先給有用資訊再提供服務，可一鍵複製、換一種說法 |
| 統計 | 現在該回、今日新增、LINE 剩餘額度、成交轉換率 |
| 資料進出 | 手動貼上單則（即時計分），或匯入爬蟲產出的 JSON 陣列 |

## 匯入格式

```json
[
  {
    "title": "iPhone 14 螢幕摔破，台北求推薦",
    "body": "昨天不小心摔到…",
    "source": "PTT MobileComm",
    "url": "https://www.ptt.cc/bbs/MobileComm/M.xxx.html",
    "author": "kkman0930",
    "posted_at": "2026-09-04T10:00:00Z"
  }
]
```

以 `url` 去重，重複的自動略過。

## 儲存

在 Claude Artifact 上執行時使用 db capability，跨裝置同步；
其他環境（例如 Cloudflare Pages 靜態託管）自動退回 localStorage，功能相同但只存在該裝置。

## 尚未實作（後端）

`crawlers/`、`core/scorer.py`、`core/notifier.py`、`.github/workflows/crawl.yml`
還沒做。前端的評分邏輯與 `config/keywords.yaml` 的結構一致，Python 版可直接對照移植。
