# 維修接單台

店面接單工單系統 ＋ PTT 維修需求爬蟲，全部包在一個資料夾裡。
下載 → 雙擊啟動 → 瀏覽器自動打開看板。**不需要 pip install 任何套件。**

---

## 一、安裝（雙擊一個檔案就好）

| 系統 | 雙擊這個 |
|---|---|
| Windows | **`安裝-Windows.bat`** |
| Mac | **`安裝-Mac.command`** |

安裝程式會自動做完這些事：

1. 檢查電腦有沒有 Python，**沒有的話幫你下載安裝**（Windows；Mac 通常內建）
2. 把所有檔案裝到**桌面的「修手機的」資料夾**
3. 在那個資料夾裡放好啟動器（Mac 另外產生「維修接單台」App）
4. 問你要不要**開機自動啟動**（店裡電腦建議開）
5. 直接啟動，瀏覽器打開 <http://127.0.0.1:8420>

裝好之後，打開桌面的**「修手機的」**資料夾，雙擊裡面的**「啟動」**就開了。
**開起來的黑色／終端機視窗不要關**，關掉程式就停了。

### 第一次打開會跳警告，這是正常的

程式沒有花錢買數位簽章，所以：

- **Windows**：SmartScreen 說「已保護您的電腦」→ 按「**其他資訊**」→「**仍要執行**」
- **Mac**：說「無法打開，因為來自未識別的開發者」→ 在檔案上**按右鍵 → 打開** → 再按一次「打開」

### 不想安裝，只想試跑

在解壓縮的資料夾直接雙擊 `啟動-Windows.bat` 或 `啟動-Mac.command`，
程式就在原地跑，不會動到系統任何地方。前提是電腦已經有 Python。

### 移除

打開桌面的「修手機的」資料夾，執行裡面的 `移除.bat`（Windows）或 `移除.command`（Mac）。
會問你要不要把工單資料留一份到桌面。Python 不會被移除。

### 想要真正的單一 exe（進階）

在 Windows 上雙擊 `build_exe.bat`，會用 PyInstaller 打包成
`dist\RepairRadar.exe`——那個 exe 拿到任何 Windows 電腦都能跑，
對方不需要有 Python。需要網路連線，第一次約 2~3 分鐘。

> 這個 exe 我沒辦法先幫你產生：打包必須在 Windows 上執行，
> 而我這邊是 Linux 環境，不能跨平台編譯。

---

## 二、開起來會看到什麼

上方兩個分頁：

### 接單（店面主用）

工單流程 `待檢測 → 報價中 → 維修中 → 待取件 → 已完成`，客戶不修按「未成交」。
每張單只有一顆綠色按鈕推進下一階段，站櫃檯單手就能操作。

- 開單填姓名、電話、機型、故障、報價、預計幾小時完成；機型與常見故障有快選鈕
- 單號自動編 `R<年月日>-序號`
- **超過預計完成時間自動紅框、排到最上面**
- 電話是可點的，手機上直接撥
- 待取件的單一鍵產生取件通知話術；報價中的單一鍵產生報價說明
- 統計：待取件、店內在修（含逾期數）、今日進單、今日營收

### 需求雷達（網路線索）

爬蟲每 10 分鐘掃一次，把「有人在找維修」的訊息抓進來評分。來源有兩類：

- **PTT 公開看板** — 不需要登入任何帳號
- **你自己的 FB 粉專與 IG 商業帳號** — 私訊與貼文留言（選配，見第四節）

**私訊不套用分數門檻。** 客人主動私訊你就是找上門的單，一律排在「現在該回」
最前面、直接推播，卡片上顯示 📩 而不是分數。留言則跟 PTT 一樣照分數排序。

- 0~100 分，每則可展開「分數怎麼算」看命中哪些關鍵字
- ≥ 70 分推 LINE，全部推 Telegram（設定見下）
- 關鍵字右上角可直接改，存檔後所有貼文即時重算
- 「立即抓取一次」按鈕可手動觸發，不用等下一輪
- 談成的線索按「轉成工單」直接進接單流程，並標記為已成交

畫面每 60 秒自動重讀資料、重算逾期時間。

---

## 三、要收到 LINE / Telegram 通知（選配）

第一次啟動會自動產生 `config.json`，用記事本打開填進去：

```json
{
  "line_channel_token": "你的 Channel access token",
  "line_user_id": "你的 User ID",
  "telegram_bot_token": "你的 Bot token",
  "telegram_chat_id": "你的 chat id"
}
```

留空就是不推播，其他功能照常。填完存檔，**重新啟動程式**才會生效。

> ⚠ 填好之後 `config.json` 就有你的金鑰。不要傳給別人，不要上傳 GitHub。
> 這個檔案已經寫進 `.gitignore`。

### 申請 LINE（約 10 分鐘）

1. 到 <https://developers.line.biz/console/> 用 LINE 帳號登入
2. 建立 Provider → 建立 **Messaging API** channel
3. 「Messaging API」分頁最下面按 **Issue** 取得 **Channel access token (long-lived)**
   → 填進 `line_channel_token`
4. 同一頁上方用手機掃 QR code 加自己的官方帳號為好友
5. 「Basic settings」分頁最下面的 **Your user ID** → 填進 `line_user_id`

免費額度每月 200 則。程式會自動控管：已用 180 則時把門檻從 70 分提高到 85 分，
已用 195 則時停止 LINE 只推 Telegram。

### 申請 Telegram（約 3 分鐘，免費無上限）

1. 在 Telegram 搜尋 `@BotFather`，傳 `/newbot`，照指示取名
2. 它會給你一串 token → 填進 `telegram_bot_token`
3. 跟你的新 bot 說一句話，然後用瀏覽器打開
   `https://api.telegram.org/bot<你的token>/getUpdates`
4. 找到 `"chat":{"id":123456789` 這個數字 → 填進 `telegram_chat_id`

---

## 四、接上粉專與 IG（選配）

抓的是**你自己擁有的**粉專與 IG 商業帳號的私訊和留言，走 Meta 官方 Graph API。

> **不會做的事：** 不登入他人帳號、不抓社團、不抓 Marketplace、不抓別人的貼文。
> 那些需要違反 Meta 使用條款的做法，會導致帳號連同你的粉專一起被停權，撐不過幾週。
> 這裡只讀取你自己有權限的資料。

### 需要什麼

1. 一個**Facebook 粉絲專頁**（你是管理員）
2. IG 也要抓的話：IG 帳號轉成**商業帳號**並連結到那個粉專

### 取得 token（約 15 分鐘）

1. 到 <https://developers.facebook.com/apps/> 建立應用程式，類型選「企業」
2. 加入產品 **Messenger** 與 **Instagram**，把你的粉專連上去
3. 打開 <https://developers.facebook.com/tools/explorer/>（Graph API 測試工具）
4. 右上選你的應用程式，權限勾選：
   `pages_show_list`、`pages_read_engagement`、`pages_messaging`、
   `pages_manage_metadata`、`instagram_basic`、`instagram_manage_comments`、
   `instagram_manage_messages`
5. 按 **Generate Access Token** 並在彈窗中授權你的粉專
6. 查詢 `me/accounts` → 找到你的粉專，`id` 填進 `meta_page_id`，
   `access_token` 填進 `meta_page_token`
7. 要抓 IG 的話，查詢 `<粉專id>?fields=instagram_business_account`
   → 取得的 id 填進 `meta_ig_user_id`

填完存檔，**重新啟動程式**。網頁「需求雷達」分頁按「來源」可確認有沒有接上。

### token 會過期

測試工具給的短期 token 大約一小時失效。要長期跑，用這個換成長期 token：

```
https://graph.facebook.com/v21.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=<你的應用程式ID>
  &client_secret=<你的應用程式密鑰>
  &fb_exchange_token=<短期token>
```

換到的粉專 token 通常不會過期。若某天視窗開始印
`Graph API 190`，就是 token 失效了，重跑一次上面的步驟。

---

## 五、常見狀況

| 狀況 | 處理 |
|---|---|
| 埠號被占用 | 改「修手機的」資料夾裡 `config.json` 的 `port`，例如 8421 |
| 想關掉開機自動啟動 | Windows：刪掉「開始→啟動」裡的捷徑。Mac：重跑安裝程式選 n |
| 檔案在哪 | 桌面的「修手機的」資料夾，全部都在裡面 |
| 安裝程式跑不起來 | Windows 在 `安裝-Windows.bat` 上按右鍵→以系統管理員身分執行 |
| 想手動跑一次爬蟲看結果 | `python3 repair_radar.py --once` |
| 只要看板不要爬蟲 | `python3 repair_radar.py --no-crawl` |
| 想換監控的看板 | 改 `config.json` 的 `ptt_boards` |
| 想改抓取頻率 | 改 `config.json` 的 `crawl_interval_minutes` |
| 想改關鍵字 | 網頁右上「關鍵字」，或直接編輯 `keywords.json` |
| 手機也想看 | 同一個 Wi-Fi 下，把 `repair_radar.py` 裡的 `127.0.0.1` 改成 `0.0.0.0`，手機開 `http://<電腦IP>:8420` |
| 資料在哪 | 同資料夾的 `data.db`（SQLite）。備份就複製這個檔案 |
| 粉專／IG 沒抓到東西 | 看視窗有沒有印 `Graph API` 錯誤。190 = token 失效、200 = 權限不足 |
| 只想抓私訊不要留言 | `config.json` 把 `meta_fetch_comments` 改成 `false` |
| 想抓更久以前的訊息 | 調大 `meta_lookback_hours`（預設 48 小時） |
| 沒有 Python 也想用 | 開 `web/維修接單台-單檔版.html`，接單功能完整，但**沒有爬蟲**，資料只存在該瀏覽器 |

---

## 六、檔案說明

```
repair-radar/
├── 安裝-Windows.bat            ★ 一鍵安裝（Windows）
├── 安裝-Mac.command            ★ 一鍵安裝（Mac）
├── build_exe.bat               選配：在 Windows 上打包成單一 exe
├── 啟動-Windows.bat            免安裝，原地執行
├── 啟動-Mac.command            免安裝，原地執行
├── tools/
│   ├── install.ps1             Windows 安裝邏輯
│   └── uninstall.ps1           Windows 移除邏輯
├── repair_radar.py             主程式：爬蟲 + 評分 + 網頁伺服器 + 推播
├── config.example.json         設定範本，第一次啟動會複製成 config.json
├── keywords.json               評分關鍵字，可自己加減
├── web/
│   ├── index.html              看板（由伺服器提供）
│   └── 維修接單台-單檔版.html   免 Python 版，無爬蟲
├── tests/
│   ├── test_scorer.py          評分與 PTT 解析測試
│   └── test_meta.py            粉專／IG 連接器測試
└── data.db                     資料（啟動後自動產生）
```

跑測試：`python3 -m unittest discover -s tests -v`

---

## 七、已知限制，先講清楚

0. **Windows 安裝程式未在真實 Windows 上跑過。** 我這邊是 Linux 環境，
   沒有 Windows 也沒有 PowerShell 可測。Windows 版是照 Mac 版同一套流程改寫的，
   語法與編碼檢查過（PowerShell 需要 UTF-8 BOM 才不會中文亂碼，已處理），
   但第一次跑請留意畫面上的訊息。出錯的話把訊息拍給我。

   Mac／Linux 這條路則是完整跑過一遍：解壓縮 → 安裝 → 從產生的啟動器開起來 →
   用真實瀏覽器操作 33 項功能（開單、推進四階段、取件話術、統計、雷達評分、
   話術生成、來源面板、重整後資料保留、主題切換）→ 驗證每分鐘自動更新
   （外部寫入一張逾期單，頁面不動作在第 60 秒自己出現並標紅）→ 測試移除程式。
   全部通過。
1. **PTT 的抓取尚未在真實網路環境驗證。** 開發環境的網路政策擋掉 `www.ptt.cc`，
   解析邏輯是照 PTT 實際 HTML 結構寫並用固定樣本測過，但真實連線請你自己跑一次
   `python3 repair_radar.py --once` 確認。抓不到會在視窗印出錯誤，不會讓程式掛掉。
2. **粉專／IG 的真實連線也未驗證。** 同樣被網路政策擋住（`graph.facebook.com`），
   而且需要真實的粉專 token。解析、去重、過濾與錯誤處理有 12 項測試覆蓋，
   但實際欄位是否如預期要你接上自己的帳號才知道。
3. **Dcard 與 Threads 沒做。** Dcard 有 Cloudflare 防護、Threads 沒有公開搜尋 API，
   不會去繞過任何防護。
4. **FB 社團與 Marketplace 不會做。** 那需要登入他人身分或規避 Meta 的限制，
   代價是帳號連同粉專一起被停權。這不是保守，是那條路真的會壞。
5. **資料存在這台電腦。** 換一台電腦看不到同一份單，除非複製 `data.db` 過去，
   或用區網共用（見上表）。
6. **成效未知。** PTT 上「新北求推薦手機維修」這類貼文一天到底有幾則，
   還沒有實測數字。建議先跑三天看撈到幾則有效需求，再決定值不值得繼續投入。
